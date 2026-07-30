import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

CHECK_DOCS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "check_docs.py"
)

_spec = importlib.util.spec_from_file_location("check_docs", CHECK_DOCS_PATH)
check_docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_docs)


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, check=True, text=True,
    )


def write(root, rel_path, content):
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return full


class TempRepo:
    """A throwaway Git repo so discover_markdown_files()/parse_make_targets()
    (both Git- and filesystem-rooted) behave exactly as in the real repo."""

    def __enter__(self):
        self.root = tempfile.mkdtemp(prefix="check-docs-test-")
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "test@example.com")
        git(self.root, "config", "user.name", "Test")
        return self

    def __exit__(self, *exc):
        pass

    def add_all(self):
        git(self.root, "add", "-A")


# ---------------------------------------------------------------------------
# Fenced-code / heading-slug / link-extraction unit tests (no Git needed)
# ---------------------------------------------------------------------------

class StripFencedBlocksTests(unittest.TestCase):
    def test_blanks_fenced_content_preserving_line_count(self):
        text = "before\n```bash\nmake all\n[fake](nope.md)\n```\nafter"
        stripped = check_docs.strip_fenced_blocks(text)
        self.assertEqual(stripped.count("\n"), text.count("\n"))
        self.assertNotIn("make all", stripped)
        self.assertIn("before", stripped)
        self.assertIn("after", stripped)

    def test_tilde_fence_supported(self):
        text = "~~~\nsome [link](x.md)\n~~~\n"
        stripped = check_docs.strip_fenced_blocks(text)
        self.assertNotIn("link", stripped)


class HeadingSlugTests(unittest.TestCase):
    def test_simple_heading(self):
        self.assertEqual(check_docs.github_heading_slug("Prerequisites"), "prerequisites")

    def test_inline_code_and_punctuation_stripped(self):
        self.assertEqual(
            check_docs.github_heading_slug("`config.mk` (root, committed)"),
            "configmk-root-committed",
        )

    def test_em_dash_produces_double_hyphen(self):
        self.assertEqual(
            check_docs.github_heading_slug("Public extension boundaries — later integration slots"),
            "public-extension-boundaries--later-integration-slots",
        )

    def test_duplicate_headings_get_numeric_suffix(self):
        text = "# Doc\n## Setup\nfoo\n## Setup\nbar\n## Setup\nbaz\n"
        slugs = check_docs.compute_heading_slugs(text)
        self.assertEqual(slugs, ["doc", "setup", "setup-1", "setup-2"])

    def test_apostrophe_and_backtick_formatting_stripped(self):
        self.assertEqual(
            check_docs.github_heading_slug("Oversized `.agbpal` with hidden trailing assets"),
            "oversized-agbpal-with-hidden-trailing-assets",
        )

    def test_explicit_suffix_collision_uses_global_used_slug_set(self):
        # Regression for issue #17 finding 10: a per-base counter dict
        # (keyed only by the un-suffixed base "foo") would independently
        # assign the *second* literal "foo-1" heading the slug "foo-1"
        # again (a silent duplicate id), instead of walking past the
        # already-used "foo-1" the way GitHub's own renderer does. The
        # sequence "foo", "foo-1", "foo" must produce three distinct,
        # GitHub-matching slugs: foo, foo-1, foo-2.
        text = "# Doc\n## foo\nbody\n## foo-1\nbody\n## foo\nbody\n"
        slugs = check_docs.compute_heading_slugs(text)
        self.assertEqual(slugs, ["doc", "foo", "foo-1", "foo-2"])
        self.assertEqual(len(slugs), len(set(slugs)), "slugs must be globally unique: %r" % (slugs,))

    def test_plain_duplicate_heading_sequence_still_correct(self):
        text = "# Doc\n## Setup\nfoo\n## Setup\nbar\n"
        slugs = check_docs.compute_heading_slugs(text)
        self.assertEqual(slugs, ["doc", "setup", "setup-1"])


class InternalLinkExtractionTests(unittest.TestCase):
    def test_finds_plain_link(self):
        stripped = check_docs.strip_fenced_blocks("See [`docs/x.md`](docs/x.md) for more.")
        targets = list(check_docs.extract_internal_link_targets(stripped))
        self.assertEqual([t for _, t in targets], ["docs/x.md"])

    def test_nested_image_link_finds_outer_target(self):
        stripped = check_docs.strip_fenced_blocks(
            "[![Build](https://example.com/badge.svg)](https://example.com/status)"
        )
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertIn("https://example.com/status", targets)

    def test_fenced_code_pseudo_links_ignored(self):
        text = "```\n[fake](does-not-exist.md)\n```\n"
        stripped = check_docs.strip_fenced_blocks(text)
        targets = list(check_docs.extract_internal_link_targets(stripped))
        self.assertEqual(targets, [])

    def test_angle_bracket_destination_with_space_supported(self):
        stripped = check_docs.strip_fenced_blocks("See [x](<docs/a b.md>) for more.")
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["docs/a b.md"])

    def test_angle_bracket_destination_with_title_supported(self):
        stripped = check_docs.strip_fenced_blocks('See [x](<docs/a b.md> "title") here.')
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["docs/a b.md"])

    def test_single_quoted_title_supported(self):
        stripped = check_docs.strip_fenced_blocks("See [x](docs/a.md 'title') for more.")
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["docs/a.md"])

    def test_uppercase_scheme_link_destination_classified_external(self):
        # Regression: the internal-link/external-URL split relies on
        # ``_is_external`` recognizing the destination's scheme -- an
        # uppercase-scheme destination like "HTTP://EXAMPLE.COM/page"
        # must still be classified external (so the internal-link
        # existence/anchor check correctly skips it instead of
        # misinterpreting it as a broken relative path, and it is instead
        # covered by the external-URL registry check -- see
        # ExternalUrlExtractionTests for that half of the contract).
        stripped = check_docs.strip_fenced_blocks("[x](HTTP://EXAMPLE.COM/page)")
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["HTTP://EXAMPLE.COM/page"])
        self.assertTrue(check_docs._is_external(targets[0]))

    # -----------------------------------------------------------------
    # Second final-verifier residual finding #3: the previous inline
    # link destination extraction used a regex that always stopped at
    # the *first* literal `)`, so any destination containing balanced
    # parentheses was silently truncated (never even reported as a
    # finding) instead of being read in full or flagged as malformed.
    # These fixtures exercise the bounded stateful scanner that replaced
    # it: balanced/nested/escaped parens, matching image syntax, and a
    # deterministic (fail-closed, not silent) outcome for genuinely
    # malformed input.
    # -----------------------------------------------------------------

    def test_balanced_parens_in_destination_not_truncated(self):
        stripped = check_docs.strip_fenced_blocks("[x](docs/a(b).md)")
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["docs/a(b).md"])

    def test_nested_balanced_parens_in_destination_not_truncated(self):
        stripped = check_docs.strip_fenced_blocks("[x](docs/a(b(c)).md)")
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["docs/a(b(c)).md"])

    def test_escaped_parens_in_destination_unescaped_for_lookup(self):
        stripped = check_docs.strip_fenced_blocks(r"[x](docs/a\(b\).md)")
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["docs/a(b).md"])

    def test_balanced_parens_in_image_destination_not_truncated(self):
        stripped = check_docs.strip_fenced_blocks("![alt](docs/a(b).png)")
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["docs/a(b).png"])

    def test_balanced_parens_with_title_after(self):
        stripped = check_docs.strip_fenced_blocks('[x](docs/a(b).md "title")')
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped)]
        self.assertEqual(targets, ["docs/a(b).md"])

    def test_missing_closing_paren_reports_error_not_silent(self):
        stripped = check_docs.strip_fenced_blocks("[x](docs/a.md")
        errors = []
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped, errors=errors)]
        self.assertEqual(targets, [])
        self.assertEqual(len(errors), 1)
        lineno, message = errors[0]
        self.assertEqual(lineno, 1)
        self.assertIn("no closing", message)

    def test_unbalanced_open_paren_in_destination_reports_error(self):
        # Two literal "(" opened but only one literal ")" closed before
        # end-of-line -- the destination itself never balances (unlike
        # test_missing_closing_paren_reports_error_not_silent, where the
        # single "(" *does* get matched by the sole ")" present, just
        # leaving no separate ")" left over to close the link itself).
        stripped = check_docs.strip_fenced_blocks("[x](docs/a(b(c.md)")
        errors = []
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped, errors=errors)]
        self.assertEqual(targets, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("unbalanced", errors[0][1])

    def test_excess_nesting_depth_reports_error(self):
        destination = "docs/" + "(" * (check_docs.MAX_LINK_DESTINATION_PAREN_DEPTH + 1) + "a.md"
        stripped = check_docs.strip_fenced_blocks("[x](%s)" % destination)
        errors = []
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped, errors=errors)]
        self.assertEqual(targets, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("nesting depth", errors[0][1])

    def test_unterminated_title_reports_error(self):
        stripped = check_docs.strip_fenced_blocks('[x](docs/a.md "unterminated)')
        errors = []
        targets = [t for _, t in check_docs.extract_internal_link_targets(stripped, errors=errors)]
        self.assertEqual(targets, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("unterminated link title", errors[0][1])

    def test_errors_default_none_still_silently_skips_malformed(self):
        # Preserves the pre-existing "no errors= given" contract used by
        # every test above this section: a malformed destination is
        # simply absent from the yielded targets, no exception raised.
        stripped = check_docs.strip_fenced_blocks("[x](docs/a.md")
        targets = list(check_docs.extract_internal_link_targets(stripped))
        self.assertEqual(targets, [])

    def test_multiple_links_multiple_lines_deterministic_line_numbers(self):
        text = (
            "line one [a](docs/a.md)\n"
            "line two, no link here\n"
            "line three [b](docs/b(c).md) and [c](docs/c.md)\n"
        )
        stripped = check_docs.strip_fenced_blocks(text)
        results = list(check_docs.extract_internal_link_targets(stripped))
        self.assertEqual(
            results,
            [
                (1, "docs/a.md"),
                (3, "docs/b(c).md"),
                (3, "docs/c.md"),
            ],
        )

    def test_fenced_code_with_parens_still_ignored(self):
        text = "```\n[fake](does(not)-exist.md)\n```\n"
        stripped = check_docs.strip_fenced_blocks(text)
        targets = list(check_docs.extract_internal_link_targets(stripped))
        self.assertEqual(targets, [])


class MalformedLinkSyntaxFindingIntegrationTests(unittest.TestCase):
    """check_internal_links() (the real production caller) must fail
    closed on malformed inline link/image syntax by emitting an actual
    Finding -- not by silently treating it as "no link here", and not by
    truncating a balanced-parenthesis destination into a bogus broken-
    link finding for the wrong (truncated) path."""

    def test_malformed_missing_close_paren_surfaces_as_finding(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a.md", "# A\n\nSee [x](docs/missing-close.md\n")
            files = ["docs/a.md"]
            findings = check_docs.check_internal_links(files, root)
            messages = [f.message for f in findings]
            self.assertTrue(any("malformed inline link/image syntax" in m for m in messages))

    def test_balanced_paren_destination_resolves_to_real_file_not_truncated(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a(b).md", "# A\n")
            write(root, "docs/c.md", "# C\n\nSee [x](a(b).md) for more.\n")
            files = ["docs/a(b).md", "docs/c.md"]
            findings = check_docs.check_internal_links(files, root)
            # The balanced-paren target must resolve to the real file that
            # actually exists at that exact path -- a naive first-`)`
            # truncation would instead look up "a(b" (missing ".md)" and
            # the trailing ")"), which does not exist, producing a false
            # broken-link finding here.
            self.assertEqual(findings, [])


class ExternalUrlExtractionTests(unittest.TestCase):
    def test_bare_url_in_inline_code_is_found(self):
        stripped = check_docs.strip_fenced_blocks("Canonical: `https://github.com/example/repo.git`")
        urls = [u for _, u in check_docs.extract_external_urls(stripped)]
        self.assertEqual(urls, ["https://github.com/example/repo.git"])

    def test_url_in_fenced_code_ignored(self):
        text = "```\nhttps://example.com/should-not-count\n```\n"
        stripped = check_docs.strip_fenced_blocks(text)
        urls = list(check_docs.extract_external_urls(stripped))
        self.assertEqual(urls, [])

    def test_trailing_punctuation_stripped(self):
        stripped = check_docs.strip_fenced_blocks("See https://example.com/page.")
        urls = [u for _, u in check_docs.extract_external_urls(stripped)]
        self.assertEqual(urls, ["https://example.com/page"])

    def test_uppercase_scheme_url_is_extracted(self):
        # Regression: a case-sensitive "https?://" pattern would silently
        # miss "HTTP://"/"HTTPS://" URLs entirely -- a total blind spot,
        # since such a link would then be misread as a relative internal
        # path by the internal-link checker too (see
        # InternalLinkExtractionTests.test_uppercase_scheme_link_destination_classified_external),
        # meaning it would never reach either check.
        stripped = check_docs.strip_fenced_blocks("Canonical: HTTP://EXAMPLE.COM/Page")
        urls = [u for _, u in check_docs.extract_external_urls(stripped)]
        self.assertEqual(urls, ["HTTP://EXAMPLE.COM/Page"])


# ---------------------------------------------------------------------------
# Internal link resolution: valid/broken/anchor/escape fixtures
# ---------------------------------------------------------------------------

class ResolveInternalLinkTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo().__enter__()
        self.root = self.repo.root
        write(self.root, "docs/a.md", "# A\n\n## Section One\n\nbody\n")
        write(self.root, "docs/b.md", "# B\nsee [a](a.md)\n")

    def test_valid_relative_link(self):
        ok, msg = check_docs.resolve_internal_link(self.root, "docs/b.md", "a.md", {})
        self.assertTrue(ok, msg)

    def test_broken_relative_link(self):
        ok, msg = check_docs.resolve_internal_link(self.root, "docs/b.md", "missing.md", {})
        self.assertFalse(ok)
        self.assertIn("does not exist", msg)

    def test_valid_anchor(self):
        ok, msg = check_docs.resolve_internal_link(self.root, "docs/b.md", "a.md#section-one", {})
        self.assertTrue(ok, msg)

    def test_broken_anchor(self):
        ok, msg = check_docs.resolve_internal_link(self.root, "docs/b.md", "a.md#no-such-section", {})
        self.assertFalse(ok)
        self.assertIn("anchor", msg)

    def test_path_escape_rejected(self):
        ok, msg = check_docs.resolve_internal_link(self.root, "docs/b.md", "../../../../etc/passwd", {})
        self.assertFalse(ok)
        self.assertIn("escapes", msg)

    def test_duplicate_heading_anchor_suffix_resolves(self):
        write(self.root, "docs/c.md", "# C\n## Setup\nx\n## Setup\ny\n")
        ok, msg = check_docs.resolve_internal_link(self.root, "docs/b.md", "c.md#setup-1", {})
        self.assertTrue(ok, msg)


# ---------------------------------------------------------------------------
# Reference-style link/image fixtures (adversarial: broken/undefined must
# never be silently 0-findings)
# ---------------------------------------------------------------------------

class ReferenceStyleLinkTests(unittest.TestCase):
    def _findings(self, root, rel_path):
        return check_docs.check_reference_style_links([rel_path], root)

    def test_valid_internal_reference_link_resolves(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a.md", "# A\n\n## Section One\n\nbody\n")
            write(root, "docs/b.md",
                  "# B\n\nSee [the A doc][a-doc] for more, "
                  "and [its section][a-section].\n\n"
                  "[a-doc]: a.md\n"
                  "[a-section]: a.md#section-one\n")
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_broken_internal_reference_link_target_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md",
                  "See [missing][ref].\n\n[ref]: does-not-exist.md\n")
            findings = self._findings(root, "docs/b.md")
            messages = [f.message for f in findings]
            self.assertTrue(any("target broken" in m and "does not exist" in m for m in messages), messages)

    def test_valid_reference_image_resolves(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/logo.png", "not-a-real-png")
            write(root, "docs/b.md", "![logo][logo-ref]\n\n[logo-ref]: logo.png\n")
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_undefined_reference_label_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md", "See [some text][never-defined] here.\n")
            findings = self._findings(root, "docs/b.md")
            messages = [f.message for f in findings]
            self.assertTrue(any("undefined reference-style link label" in m and "never-defined" in m for m in messages), messages)

    def test_collapsed_reference_resolves_using_text_as_label(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a.md", "# A\n")
            write(root, "docs/b.md", "See [a.md][] here.\n\n[a.md]: a.md\n")
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_collapsed_reference_undefined_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md", "See [nope][] here.\n")
            findings = self._findings(root, "docs/b.md")
            messages = [f.message for f in findings]
            self.assertTrue(any("undefined reference-style link label" in m for m in messages), messages)

    def test_label_matching_is_case_and_whitespace_insensitive(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a.md", "# A\n")
            write(root, "docs/b.md", "See [text][My   Label] here.\n\n[my label]: a.md\n")
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_duplicate_definition_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a.md", "# A\n")
            write(root, "docs/other.md", "# Other\n")
            write(root, "docs/b.md",
                  "See [text][dup].\n\n[dup]: a.md\n[dup]: other.md\n")
            findings = self._findings(root, "docs/b.md")
            messages = [f.message for f in findings]
            self.assertTrue(any("duplicate reference-style link definition" in m and "dup" in m for m in messages), messages)

    def test_malformed_definition_missing_destination_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md", "See [text][broken].\n\n[broken]:\n")
            findings = self._findings(root, "docs/b.md")
            messages = [f.message for f in findings]
            self.assertTrue(any("malformed reference-style link definition" in m and "missing destination" in m for m in messages), messages)

    def test_fenced_code_reference_syntax_ignored(self):
        with TempRepo() as repo:
            root = repo.root
            text = (
                "See prose.\n\n"
                "```\n"
                "[fake][undefined-in-code]\n"
                "[undefined-in-code]: does-not-exist.md\n"
                "```\n"
            )
            write(root, "docs/b.md", text)
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_inline_code_bracket_text_not_treated_as_reference_link(self):
        # Regression fixture: a shell regex character class inside inline
        # code (e.g. `grep -E '[89][0-9A-Fa-f]{6}'`) must never be parsed
        # as a `[text][label]` reference usage -- a code span's contents
        # are never re-parsed as link syntax by any real Markdown renderer.
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md",
                  "Run `grep -E '0x0[89][0-9A-Fa-f]{6}'` to audit pointers.\n")
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_shortcut_reference_matching_defined_label_reported_unsupported(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a.md", "# A\n")
            write(root, "docs/b.md",
                  "See [My Label] for details.\n\n[my label]: a.md\n")
            findings = self._findings(root, "docs/b.md")
            messages = [f.message for f in findings]
            self.assertTrue(
                any("unsupported" in m and "shortcut" in m and "My Label" in m for m in messages),
                messages,
            )

    def test_shortcut_bracket_text_not_matching_any_label_is_not_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md", "Some prose with [a bracketed phrase] in it.\n")
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_task_list_checkbox_not_flagged_as_shortcut(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md", "- [ ] todo\n- [x] done\n")
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_inline_link_not_double_flagged_by_shortcut_scan(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a.md", "# A\n")
            write(root, "docs/b.md", "[a.md]: a.md\n\nSee [a.md](a.md) for more.\n")
            findings = self._findings(root, "docs/b.md")
            self.assertEqual(findings, [])

    def test_external_registered_reference_definition_passes_full_pipeline(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md",
                  "See [upstream][up] for context.\n\n"
                  "[up]: https://example.com/page\n")
            write(
                root, check_docs.REGISTRY_PATH,
                "# Registry\n\n" + check_docs.REGISTRY_BEGIN + "\n"
                "- host:example.com | alice | third-party-reference | n\n"
                + check_docs.REGISTRY_END + "\n",
            )
            ref_findings = self._findings(root, "docs/b.md")
            self.assertEqual(ref_findings, [])
            rules, errors = check_docs.parse_registry(root)
            self.assertEqual(errors, [])
            url_findings = check_docs.check_external_urls(["docs/b.md"], root, rules)
            self.assertEqual(url_findings, [])

    def test_external_unregistered_reference_definition_flagged_by_url_check(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/b.md",
                  "See [upstream][up] for context.\n\n"
                  "[up]: https://not-covered.example.com/page\n")
            write(
                root, check_docs.REGISTRY_PATH,
                "# Registry\n\n" + check_docs.REGISTRY_BEGIN + "\n"
                "- host:example.com | alice | third-party-reference | n\n"
                + check_docs.REGISTRY_END + "\n",
            )
            ref_findings = self._findings(root, "docs/b.md")
            self.assertEqual(ref_findings, [])  # external target: not this checker's job
            rules, errors = check_docs.parse_registry(root)
            self.assertEqual(errors, [])
            url_findings = check_docs.check_external_urls(["docs/b.md"], root, rules)
            messages = [f.message for f in url_findings]
            self.assertTrue(any("not covered" in m for m in messages), messages)

    def test_malformed_title_after_destination_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "docs/a.md", "# A\n")
            write(root, "docs/b.md", "See [text][t].\n\n[t]: a.md unquoted trailing junk\n")
            findings = self._findings(root, "docs/b.md")
            messages = [f.message for f in findings]
            self.assertTrue(any("malformed reference-style link definition title" in m for m in messages), messages)


# ---------------------------------------------------------------------------
# Inventory parsing/coverage fixtures
# ---------------------------------------------------------------------------

class InventoryTests(unittest.TestCase):
    def _write_inventory(self, root, entries_block):
        content = (
            "# Inventory\n\n"
            + check_docs.INVENTORY_BEGIN + "\n"
            + entries_block + "\n"
            + check_docs.INVENTORY_END + "\n"
        )
        write(root, check_docs.INVENTORY_PATH, content)

    def test_valid_inventory_matches_files(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.md", "# A\n")
            self._write_inventory(root, "- a.md | alice | current | test doc\n"
                                         "- " + check_docs.INVENTORY_PATH + " | alice | current | inventory")
            entries, errors = check_docs.parse_inventory(root)
            self.assertEqual(errors, [])
            files = check_docs.discover_markdown_files(root)
            # untracked is fine for discovery; add so it's picked up deterministically
            findings = check_docs.check_inventory_coverage(root, files, entries)
            self.assertEqual(findings, [])

    def test_missing_entry_detected(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.md", "# A\n")
            write(root, "b.md", "# B\n")
            self._write_inventory(root, "- a.md | alice | current | test doc\n"
                                         "- " + check_docs.INVENTORY_PATH + " | alice | current | inventory")
            entries, _ = check_docs.parse_inventory(root)
            files = check_docs.discover_markdown_files(root)
            findings = check_docs.check_inventory_coverage(root, files, entries)
            messages = [f.message for f in findings]
            self.assertTrue(any("b.md" in m and "missing" in m for m in messages))

    def test_extra_entry_detected(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.md", "# A\n")
            self._write_inventory(root, "- a.md | alice | current | test doc\n"
                                         "- ghost.md | alice | current | does not exist\n"
                                         "- " + check_docs.INVENTORY_PATH + " | alice | current | inventory")
            entries, _ = check_docs.parse_inventory(root)
            files = check_docs.discover_markdown_files(root)
            findings = check_docs.check_inventory_coverage(root, files, entries)
            messages = [f.message for f in findings]
            self.assertTrue(any("ghost.md" in m for m in messages))

    def test_invalid_status_rejected(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.md", "# A\n")
            self._write_inventory(root, "- a.md | alice | not-a-real-status | test doc")
            _, errors = check_docs.parse_inventory(root)
            self.assertTrue(any("invalid status" in e for e in errors))

    def test_missing_owner_rejected(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.md", "# A\n")
            self._write_inventory(root, "- a.md |  | current | test doc")
            _, errors = check_docs.parse_inventory(root)
            self.assertTrue(any("empty owner" in e for e in errors))


# ---------------------------------------------------------------------------
# External-link registry fixtures
# ---------------------------------------------------------------------------

class RegistryTests(unittest.TestCase):
    def _write_registry(self, root, rules_block):
        content = (
            "# Registry\n\n"
            + check_docs.REGISTRY_BEGIN + "\n"
            + rules_block + "\n"
            + check_docs.REGISTRY_END + "\n"
        )
        write(root, check_docs.REGISTRY_PATH, content)

    def test_host_and_prefix_rules_parse(self):
        with TempRepo() as repo:
            root = repo.root
            self._write_registry(
                root,
                "- host:example.com | alice | third-party-reference | notes\n"
                "- prefix:https://github.com/laqieer/fireemblem8u | alice | historical-upstream | upstream",
            )
            rules, errors = check_docs.parse_registry(root)
            self.assertEqual(errors, [])
            self.assertEqual(len(rules), 2)

    def test_malformed_url_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "See `https:///no-host` for details.\n")
            self._write_registry(root, "- host:example.com | alice | third-party-reference | n")
            rules, _ = check_docs.parse_registry(root)
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            self.assertTrue(any("malformed" in f.message for f in findings))

    def test_unregistered_url_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "See https://not-covered.example.com/page for details.\n")
            self._write_registry(root, "- host:example.com | alice | third-party-reference | n")
            rules, _ = check_docs.parse_registry(root)
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            self.assertTrue(any("not covered" in f.message for f in findings))

    def test_fireemblem8u_url_requires_historical_upstream_status(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "See https://github.com/laqieer/fireemblem8u/wiki for details.\n")
            self._write_registry(
                root,
                "- prefix:https://github.com/laqieer/fireemblem8u | alice | authoritative-self | wrong status",
            )
            rules, _ = check_docs.parse_registry(root)
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            self.assertTrue(any("historical-upstream" in f.message for f in findings))

    def test_fireemblem8u_url_with_correct_status_passes(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "See https://github.com/laqieer/fireemblem8u/wiki for details.\n")
            self._write_registry(
                root,
                "- prefix:https://github.com/laqieer/fireemblem8u | alice | historical-upstream | ok",
            )
            rules, _ = check_docs.parse_registry(root)
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            self.assertEqual(findings, [])

    def test_bad_match_type_prefix_rejected(self):
        with TempRepo() as repo:
            root = repo.root
            self._write_registry(root, "- example.com | alice | third-party-reference | missing host:/prefix:")
            _, errors = check_docs.parse_registry(root)
            self.assertTrue(any("must start with" in e for e in errors))

    def _registry_and_rules(self, repo, rules_block):
        root = repo.root
        self._write_registry(root, rules_block)
        rules, errors = check_docs.parse_registry(root)
        self.assertEqual(errors, [])
        return root, rules

    def test_prefix_lookalike_hyphen_suffix_rejected_even_with_generic_host_fallback(self):
        # Adversarial regression for issue #17 finding 7/8: a lookalike
        # repo name that merely shares the registered fireemblem8u prefix
        # as a literal string ("fireemblem8u-evil") must still be
        # rejected, even though the doc/registry also carries a broad
        # ``host:github.com`` fallback rule that would otherwise happily
        # accept *any* github.com URL, including this spoof.
        with TempRepo() as repo:
            root, rules = self._registry_and_rules(
                repo,
                "- prefix:https://github.com/laqieer/fireemblem8u | alice | historical-upstream | upstream\n"
                "- host:github.com | alice | third-party-reference | generic github fallback",
            )
            write(root, "doc.md", "See https://github.com/laqieer/fireemblem8u-evil for details.\n")
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            messages = [f.message for f in findings]
            self.assertTrue(any("upstream-lookalike" in m or "lookalike" in m for m in messages), messages)

    def test_prefix_lookalike_dot_suffix_rejected(self):
        with TempRepo() as repo:
            root, rules = self._registry_and_rules(
                repo,
                "- prefix:https://github.com/laqieer/fireemblem8u | alice | historical-upstream | upstream\n"
                "- host:github.com | alice | third-party-reference | generic github fallback",
            )
            write(root, "doc.md", "See https://github.com/laqieer/fireemblem8u.evil.example for details.\n")
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            messages = [f.message for f in findings]
            self.assertTrue(any("lookalike" in m for m in messages), messages)

    def test_legitimate_git_clone_suffix_still_passes(self):
        # ".git" is the standard, legitimate way to write this exact
        # upstream repository's clone URL -- it must classify the same as
        # any other real subpath, not as a lookalike continuation.
        with TempRepo() as repo:
            root, rules = self._registry_and_rules(
                repo,
                "- prefix:https://github.com/laqieer/fireemblem8u | alice | historical-upstream | upstream",
            )
            write(root, "doc.md", "Clone: `https://github.com/laqieer/fireemblem8u.git`\n")
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            self.assertEqual(findings, [])

    def test_scheme_and_host_case_normalized_for_registry_match(self):
        with TempRepo() as repo:
            root, rules = self._registry_and_rules(
                repo, "- host:example.com | alice | third-party-reference | n",
            )
            write(root, "doc.md", "See HTTPS://EXAMPLE.COM/Page for details.\n")
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            self.assertEqual(findings, [])

    def test_query_and_fragment_on_legitimate_upstream_url_pass(self):
        with TempRepo() as repo:
            root, rules = self._registry_and_rules(
                repo,
                "- prefix:https://github.com/laqieer/fireemblem8u | alice | historical-upstream | upstream",
            )
            write(root, "doc.md",
                  "See https://github.com/laqieer/fireemblem8u/wiki?tab=readme#history for details.\n")
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            self.assertEqual(findings, [])

    def test_ordinary_other_github_repo_link_still_governed_by_normal_registry_rules(self):
        with TempRepo() as repo:
            root, rules = self._registry_and_rules(
                repo, "- host:github.com | alice | third-party-reference | n",
            )
            write(root, "doc.md", "See https://github.com/someorg/unrelated-repo for details.\n")
            findings = check_docs.check_external_urls(["doc.md"], root, rules)
            self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# Stale-phrase denylist fixtures
# ---------------------------------------------------------------------------

class StalePhraseTests(unittest.TestCase):
    def test_stale_decomp_tutorial_pointer_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "The decomp tutorial in `CONTRIBUTING.md` walks a full function.\n")
            findings = check_docs.check_stale_phrases(["doc.md"], root)
            self.assertTrue(findings)

    def test_stale_quickstart_agbcc_claim_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "Setup (installs agbcc + builds the `tools/`): run it.\n")
            findings = check_docs.check_stale_phrases(["doc.md"], root)
            self.assertTrue(findings)

    def test_clean_doc_has_no_stale_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "This project uses a modern toolchain by default.\n")
            findings = check_docs.check_stale_phrases(["doc.md"], root)
            self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# Issue #17 verifier finding regression: docs/quickstart.md previously
# hardcoded modern-object counts (18/21/363/435/438) that drifted out of
# sync with modern.mk's actual MODERN_COHORT_*/MODERN_ALL_* variables. Each
# stale phrase below must be flagged, and the replacement dynamic
# `make print-<VAR>` wording must both stay clean and resolve against the
# real, statically-parsed Makefile/modern.mk target database (never
# invoking `make`).
# ---------------------------------------------------------------------------

REAL_REPO_ROOT = os.path.dirname(os.path.dirname(CHECK_DOCS_PATH))


class StaleQuickstartObjectCountRegressionTests(unittest.TestCase):
    OLD_STALE_PHRASES = [
        "as twenty-one `.o` and twenty-one `.d` files.",
        "all 435 authoritative C files (363 normal `src/*.c`,",
        "since the 18-file cohort is a strict subset of the",
        "363-file full C list) as 438 `.o` and 438 primary `.d` files.",
        "links a full modern ELF using all 438 modern objects,",
    ]

    def test_each_old_quickstart_phrase_is_flagged_stale(self):
        for phrase in self.OLD_STALE_PHRASES:
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_stale_phrases(["doc.md"], root)
                self.assertTrue(findings, "expected a finding for: %r" % phrase)

    def test_current_quickstart_object_wording_has_no_stale_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "quickstart.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "docs", "quickstart.md")
            ))
            findings = check_docs.check_stale_phrases(["quickstart.md"], root)
            self.assertEqual(findings, [])

    # The replacement `make print-<VAR>` commands quickstart.md now
    # documents must resolve against this repository's real, statically
    # parsed Makefile/modern.mk target graph, proving they are not
    # illustrative placeholders.
    def test_dynamic_print_commands_resolve_against_real_makefile(self):
        literal, patterns = check_docs.parse_make_targets(REAL_REPO_ROOT)
        for var in (
            "MODERN_COHORT_C_OBJECTS",
            "MODERN_COHORT_ASM_OBJECTS",
            "MODERN_COHORT_OBJECTS",
            "MODERN_ALL_C_OBJECTS",
            "MODERN_ALL_DATA_OBJECTS",
            "MODERN_ALL_ASM_OBJECTS",
            "MODERN_ALL_OBJECTS",
        ):
            with self.subTest(var=var):
                self.assertTrue(
                    check_docs.make_target_exists("print-" + var, literal, patterns),
                    "print-%s should resolve via the print-%% pattern rule" % var,
                )


# ---------------------------------------------------------------------------
# Acceptance-review finding (issues #7/#17 docs contract fixup): the same
# 3-defect pattern found earlier in quickstart.md was later reintroduced in
# docs/framework-support.md by a subsequent governance-establishing commit:
#
#   1. docs/framework-support.md hardcoded MODERN_COHORT_OBJECTS/
#      MODERN_ALL_OBJECTS counts (21 C + 3 asm = 24; 450) instead of
#      pointing solely at `make print-<VAR>`.
#   2. Its expansion-modern-elf row listed `MODERN_ABI=<aapcs|apcs-gnu>` as
#      if both ABIs were valid for a *linked* target, when modern.mk's
#      MODERN_LINKED_GOALS guard fails fast on anything but aapcs.
#   3. docs/config_identity.md's MODERN_ABI settings-reference row carried
#      no caveat that apcs-gnu is compile-only.
#
# The tests below prove (a) the old phrasing is flagged stale if it ever
# reappears, (b) the current, live doc text is both stale-clean and states
# the AAPCS-only/apcs-gnu-compile-only contract explicitly, and (c) that
# contract is real -- proven against the actual `modern.mk` via a real
# `make -n` dry-run probe, never a simulated/equivalent stand-in.
# ---------------------------------------------------------------------------

class StaleFrameworkSupportABIRegressionTests(unittest.TestCase):
    OLD_STALE_PHRASES = [
        "21 `src/*.c` objects + 3 handwritten-assembly objects, 24 total",
        "handwritten asm: 450 objects as of this audit",
        r"expansion-modern-elf MODERN_CONFIG=<debug\|release> MODERN_ABI=<aapcs\|apcs-gnu>",
    ]

    def test_each_old_phrase_is_flagged_stale(self):
        for phrase in self.OLD_STALE_PHRASES:
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_stale_phrases(["doc.md"], root)
                self.assertTrue(findings, "expected a finding for: %r" % phrase)

    def test_current_framework_support_wording_has_no_stale_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "framework-support.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "docs", "framework-support.md")
            ))
            findings = check_docs.check_stale_phrases(["framework-support.md"], root)
            self.assertEqual(findings, [])

    def test_current_config_identity_wording_has_no_stale_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "config_identity.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "docs", "config_identity.md")
            ))
            findings = check_docs.check_stale_phrases(["config_identity.md"], root)
            self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# Issues #7/#17 independent-verifier finding: two stale current-facts
# reintroduced after the #7/#17 docs integration --
#
#   1. docs/generated_data.md and reports/generated_data_issue5_closure.md
#      asserted GitHub issue #5 was still OPEN with no merged state. #5 is
#      now CLOSED (closed 2026-07-25), with completion commit
#      ac0ee5d7f17eb8e70175576cb46d9f320d8013cd merged into master.
#   2. docs/framework-support.md said the item-ID-expansion checks were
#      "gates 11-12" of the upstream verify gate set; the real, current
#      scripts/upstream_port/verify.py gates() puts them at indexes 9-10
#      of exactly 10.
#
# These tests prove: (a) every old phrase is flagged stale if it reappears,
# (b) the current live doc/report text is stale-clean, (c) the historical,
# batch-scoped technical boundary wording (which looks similar but is not a
# live current-status claim) is NOT flagged, (d) the current docs/report
# state #5 CLOSED with the real completion commit as merged evidence, and
# (e) the "gates 9-10" claim is source-backed against the real
# scripts/upstream_port/verify.py gates() ordering -- never a hardcoded
# fake substitute.
# ---------------------------------------------------------------------------

class StaleIssue5StatusAndGateNumberRegressionTests(unittest.TestCase):
    OLD_STALE_PHRASES = [
        "GitHub issue #5 is still **OPEN** (this repository does not close it),",
        "#5 is OPEN at time of writing",
        "Does not close GitHub issue #5 (OPEN).",
        "gates 11-12 of",
    ]

    def test_each_old_phrase_is_flagged_stale(self):
        for phrase in self.OLD_STALE_PHRASES:
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_stale_phrases(["doc.md"], root)
                self.assertTrue(findings, "expected a finding for: %r" % phrase)

    def test_batch_scoped_non_goal_wording_not_flagged(self):
        # These look superficially similar (mention Issue #5 + "not
        # closed"/"open") but are historical, batch-scoped technical
        # boundary statements, not a live current-status claim -- they
        # must stay clean.
        preserved_phrases = [
            "Issue #5 itself is **not closed** by Batch A/B.",
            "but this still does **not** close Issue #5.",
            "does not close Issue #5's mechanics scope, nor Issue #5 overall.",
            "remains open scope for a future batch, if ever appropriate",
        ]
        for phrase in preserved_phrases:
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_stale_phrases(["doc.md"], root)
                self.assertEqual(findings, [], "unexpected finding for: %r" % phrase)

    def test_current_generated_data_doc_has_no_stale_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "generated_data.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "docs", "generated_data.md")
            ))
            findings = check_docs.check_stale_phrases(["generated_data.md"], root)
            self.assertEqual(findings, [])

    def test_current_framework_support_doc_has_no_stale_findings_for_gate_numbers(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "framework-support.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "docs", "framework-support.md")
            ))
            findings = check_docs.check_stale_phrases(["framework-support.md"], root)
            self.assertEqual(findings, [])

    def test_current_issue5_closure_report_has_no_stale_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "generated_data_issue5_closure.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "reports", "generated_data_issue5_closure.md")
            ))
            findings = check_docs.check_stale_phrases(
                ["generated_data_issue5_closure.md"], root
            )
            self.assertEqual(findings, [])

    def test_current_docs_state_issue5_closed_with_merged_commit_evidence(self):
        completion_commit = "ac0ee5d7f17eb8e70175576cb46d9f320d8013cd"
        generated_data_text = check_docs.read_text(
            os.path.join(REAL_REPO_ROOT, "docs", "generated_data.md")
        )
        closure_report_text = check_docs.read_text(
            os.path.join(REAL_REPO_ROOT, "reports", "generated_data_issue5_closure.md")
        )
        self.assertIn("GitHub issue #5 is **CLOSED**", generated_data_text)
        self.assertIn(completion_commit, generated_data_text)
        self.assertIn("#5 is CLOSED", closure_report_text)
        self.assertIn(completion_commit, closure_report_text)
        self.assertNotIn("is still **OPEN**", generated_data_text)
        self.assertNotIn("OPEN at time of writing", closure_report_text)

    def test_framework_support_states_item_expansion_gates_9_10(self):
        framework_support_text = check_docs.read_text(
            os.path.join(REAL_REPO_ROOT, "docs", "framework-support.md")
        )
        self.assertIn("gates 9-10 of", framework_support_text)
        self.assertNotIn("gates 11-12", framework_support_text)

    def test_verify_gates_item_expansion_entries_are_indexes_9_and_10_of_10(self):
        # Safe, standalone, no-network import of the live verify module
        # straight off disk -- proves "gates 9-10" against the real,
        # current scripts/upstream_port/verify.py gates() ordering rather
        # than a hardcoded fake substitute.
        verify_path = os.path.join(
            REAL_REPO_ROOT, "scripts", "upstream_port", "verify.py"
        )
        spec = importlib.util.spec_from_file_location(
            "issue5_gate_regression_verify_standalone", verify_path
        )
        verify_mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = verify_mod
        try:
            spec.loader.exec_module(verify_mod)
            all_gates = verify_mod.gates(jobs=2)
        finally:
            sys.modules.pop(spec.name, None)

        self.assertEqual(len(all_gates), 10)
        # Gates are 1-indexed in the docs ("gates 9-10"); Python lists are
        # 0-indexed, so that's positions [8] and [9].
        self.assertIn("itemexpansion", all_gates[8].name)
        self.assertIn("itemexpansion", all_gates[9].name)
        for gate in all_gates[:8]:
            self.assertNotIn("itemexpansion", gate.name)


class ABIFactualDocContractTests(unittest.TestCase):
    """Focused ABI factual tests: read the real, live doc files off disk
    (never a copy/paraphrase) and assert the linked-output-vs-compile-only
    ABI contract is stated correctly."""

    def _framework_support_text(self):
        return check_docs.read_text(os.path.join(REAL_REPO_ROOT, "docs", "framework-support.md"))

    def _config_identity_text(self):
        return check_docs.read_text(os.path.join(REAL_REPO_ROOT, "docs", "config_identity.md"))

    def test_linked_elf_row_states_aapcs_only(self):
        text = self._framework_support_text()
        self.assertIn(
            r"make expansion-modern-elf MODERN_CONFIG=<debug\|release> MODERN_ABI=aapcs`",
            text,
        )
        # The old ambiguous dual-ABI notation must not be present.
        self.assertNotIn(r"MODERN_ABI=<aapcs\|apcs-gnu>", text)

    def test_rom_boot_check_linker_check_rows_state_aapcs_only(self):
        text = self._framework_support_text()
        for target in (
            "expansion-modern-rom",
            "expansion-modern-boot-check",
            "expansion-modern-linker-check",
        ):
            with self.subTest(target=target):
                self.assertIn("make %s MODERN_CONFIG=... MODERN_ABI=aapcs`" % target, text)

    def test_abi_contract_note_present_and_explicit(self):
        text = self._framework_support_text()
        self.assertIn("**ABI contract:**", text)
        self.assertIn("is the only supported choice for every", text)
        self.assertIn("fails fast in `modern.mk`", text)

    def test_cohort_and_all_rows_document_compile_only_apcs_gnu(self):
        text = self._framework_support_text()
        self.assertIn(
            "Accepts `MODERN_ABI=aapcs` (default) or `MODERN_ABI=apcs-gnu`; "
            "neither ABI choice links here, so both are safe compile-only comparisons",
            text,
        )
        self.assertIn(
            "Accepts `MODERN_ABI=apcs-gnu` for the same compile-only comparison "
            "use as `expansion-modern-cohort` above.",
            text,
        )

    def test_config_identity_carries_apcs_gnu_compile_only_caveat(self):
        text = self._config_identity_text()
        self.assertIn("accepted only by the compile-only", text)
        self.assertIn("requires `MODERN_ABI=aapcs` and fails fast", text)

    def test_no_hardcoded_cohort_or_all_object_counts_remain(self):
        text = self._framework_support_text()
        for stale_number_phrase in ("24 total", "450 objects"):
            with self.subTest(phrase=stale_number_phrase):
                self.assertNotIn(stale_number_phrase, text)


class RealMakeDryRunABIContractProbeTests(unittest.TestCase):
    """Real, executed `make -n` (dry-run, never invokes a recipe) probes
    against this repository's actual modern.mk -- not a simulated or
    equivalent source-level stand-in -- proving the documented ABI
    contract is what the build system actually enforces today. `-n`
    guarantees no compiler/assembler/linker command is ever run; the
    linked-goal guard in modern.mk is evaluated during Makefile parsing,
    before any recipe would even be dry-run-printed."""

    def _run(self, *args, timeout=60):
        return subprocess.run(
            ["make", "-n", *args],
            cwd=REAL_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def test_linked_elf_apcs_gnu_fails_fast_without_linking(self):
        result = self._run(
            "expansion-modern-elf", "MODERN_CONFIG=debug", "MODERN_ABI=apcs-gnu",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        combined = result.stdout + result.stderr
        self.assertIn("requires MODERN_ABI=aapcs", combined)
        self.assertIn("apcs-gnu objects are", combined)
        # The guard must fire before any compiler/linker command line is
        # ever dry-run-printed for this goal.
        self.assertNotIn("arm-none-eabi-gcc", combined)
        self.assertNotIn("arm-none-eabi-ld", combined)

    def test_linked_elf_aapcs_dry_run_does_not_fail_fast(self):
        result = self._run(
            "expansion-modern-elf", "MODERN_CONFIG=debug", "MODERN_ABI=aapcs",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("requires MODERN_ABI=aapcs", result.stdout + result.stderr)

    def test_cohort_apcs_gnu_compile_only_dry_run_succeeds(self):
        result = self._run(
            "expansion-modern-cohort", "MODERN_CONFIG=debug", "MODERN_ABI=apcs-gnu",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_apcs_gnu_compile_only_dry_run_succeeds(self):
        result = self._run(
            "expansion-modern-all", "MODERN_CONFIG=debug", "MODERN_ABI=apcs-gnu",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# Issue #17 checker-escape regression: reports/issue17_documentation_audit.md
# kept hardcoded MODERN_COHORT_*/MODERN_ALL_* object-count numbers (some
# inside fenced ```bash/```text blocks) even after the equivalent prose
# claims in docs/quickstart.md and docs/framework-support.md had already
# been fixed, because check_stale_phrases() strips fenced code blocks
# before scanning and only matches a fixed literal-phrase denylist.
# check_object_count_claims() closes that escape with context-based (not
# literal-phrase) patterns applied to raw text (fenced code included).
# These fixtures use the *actual* phrases the verifier found still present
# in that report, prove they are flagged regardless of fencing, prove the
# same content is flagged regardless of its registered
# docs/documentation-inventory.md status, and prove a bare dynamic
# `make print-<VAR>` command still passes.
# ---------------------------------------------------------------------------

class ObjectCountClaimEscapeRegressionTests(unittest.TestCase):
    # Verbatim phrases the verifier found still present in
    # reports/issue17_documentation_audit.md before this round's fix.
    REAL_REPORT_PHRASES = [
        "make print-MODERN_COHORT_OBJECTS      # -> 24 objects total",
        "make print-MODERN_ALL_OBJECTS         # -> 450 objects as of this audit (wildcard-derived, drifts)",
        "MODERN_COHORT_C_OBJECTS=21, MODERN_COHORT_ASM_OBJECTS=3, MODERN_COHORT_OBJECTS=24 total",
        "(375+72=447)",
        "(363 + 72 = 435, not accounting for the 3 asm files claimed separately;",
        "its own counts (21 cohort C + 3 asm = 24; 450 all-objects) match",
        "cohort C sources = 21",
        "make print-MODERN_ALL_OBJECTS         # -> 450",
    ]

    def test_each_real_report_phrase_is_flagged(self):
        for phrase in self.REAL_REPORT_PHRASES:
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_object_count_claims(["doc.md"], root)
                self.assertTrue(findings, "expected a finding for: %r" % phrase)

    def test_flagged_even_inside_fenced_code_block(self):
        # This is the exact escape hatch: check_stale_phrases() strips
        # fenced blocks, so a hardcoded count hidden inside one previously
        # produced zero findings. check_object_count_claims() must not.
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md",
                  "```bash\n"
                  "make print-MODERN_ALL_OBJECTS         # -> 450 objects as of this audit\n"
                  "```\n")
            stale_findings = check_docs.check_stale_phrases(["doc.md"], root)
            self.assertEqual(stale_findings, [], "expected the fenced-block escape to reproduce")
            findings = check_docs.check_object_count_claims(["doc.md"], root)
            self.assertTrue(findings, "check_object_count_claims must still catch it")

    def test_dynamic_print_command_alone_passes(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md",
                  "```bash\n"
                  "make print-MODERN_COHORT_OBJECTS\n"
                  "make print-MODERN_ALL_OBJECTS\n"
                  "```\n")
            findings = check_docs.check_object_count_claims(["doc.md"], root)
            self.assertEqual(findings, [])

    def test_unrelated_object_word_and_hex_arithmetic_do_not_false_positive(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md",
                  "[A] HIGH-CONFIDENCE ... : 0 in 0 object(s)\n"
                  "End offset `0x080DFA2C + 5944 = 0x080E1164` lands exactly on the block.\n"
                  "`UnitDef_Ch2Enemy_1`, `UnitDef_Ch2Enemy_2` (5/6/2/1/2/2/1 units respectively).\n")
            findings = check_docs.check_object_count_claims(["doc.md"], root)
            self.assertEqual(findings, [])

    def test_current_report_has_no_object_count_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "issue17_documentation_audit.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "reports", "issue17_documentation_audit.md")
            ))
            findings = check_docs.check_object_count_claims(
                ["issue17_documentation_audit.md"], root
            )
            self.assertEqual(findings, [])

    def _run_full_checks_with_status(self, status):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "make print-MODERN_ALL_OBJECTS         # -> 450 objects\n")
            write(root, check_docs.INVENTORY_PATH,
                  "# Inventory\n\n" + check_docs.INVENTORY_BEGIN + "\n"
                  + "- doc.md | alice | %s | test doc\n" % status
                  + "- " + check_docs.INVENTORY_PATH + " | alice | current | inventory\n"
                  + check_docs.INVENTORY_END + "\n")
            write(root, check_docs.REGISTRY_PATH,
                  "# Registry\n\n" + check_docs.REGISTRY_BEGIN + "\n"
                  + check_docs.REGISTRY_END + "\n")
            findings, _, _ = check_docs.run_checks(root)
            return findings

    def test_object_count_claim_fails_regardless_of_evidence_status(self):
        findings = self._run_full_checks_with_status("evidence")
        self.assertTrue(any("object-count" in f.message for f in findings))

    def test_object_count_claim_fails_regardless_of_historical_status(self):
        findings = self._run_full_checks_with_status("historical")
        self.assertTrue(any("object-count" in f.message for f in findings))


# ---------------------------------------------------------------------------
# Second final-verifier residual finding #1: check_object_count_claims()
# only matched a *digit* count -- docs/quickstart.md carried the exact same
# drift-prone claim spelled out in English words instead ("three
# handwritten assembly files", "the five save objects"), which slipped
# through untouched. OBJECT_COUNT_SPELLED_RE closes that escape with a
# closed, deterministic number-word token set (zero..twenty plus the
# hyphenated twenty-one..twenty-nine tens) paired with this codebase's own
# object/source noun vocabulary, scanned across the *whole* raw file text
# (not per line) so a phrase this project's own soft-wrapped prose style
# splits across a line break is still caught. These fixtures use the
# *actual* old phrasing (including its real line-wrapped shape) that was
# present in docs/quickstart.md before this round's fix, plus synthetic
# positive/negative fixtures proving the noise-avoidance contract.
# ---------------------------------------------------------------------------

class SpelledObjectCountClaimRegressionTests(unittest.TestCase):
    # Verbatim (including the real line-wrap point) phrases the verifier
    # found still present in docs/quickstart.md before this round's fix.
    REAL_OLD_QUICKSTART_PHRASES = [
        "rather than trusting a number written here) and three handwritten assembly\n"
        "files to ARM relocatable objects only.",
        "The cohort also assembles three handwritten files that must not be\n"
        "decompiled",
        "build/expansion-modern/<config>/<abi>/` (C objects under `src/`, the three\n"
        "handwritten assembly objects under `src/` and `asm/`",
        "The modern\n"
        "`ap.o`, the five save objects (`bmsave-misc.o`, `bmsave-gmap.o`,",
    ]

    def test_each_real_old_quickstart_phrase_is_flagged(self):
        for phrase in self.REAL_OLD_QUICKSTART_PHRASES:
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_object_count_claims(["doc.md"], root)
                self.assertTrue(findings, "expected a finding for: %r" % phrase)

    def test_synthetic_positive_fixtures_are_flagged(self):
        for phrase in (
            "eighteen C files were compiled for the cohort.",
            "twenty-one asm sources are promoted together.",
            "the seven data objects are compile-only.",
            "This links four assembly files into the cohort.",
        ):
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_object_count_claims(["doc.md"], root)
                self.assertTrue(findings, "expected a finding for: %r" % phrase)

    def test_ordinary_prose_and_unrelated_counts_do_not_false_positive(self):
        for phrase in (
            "This is one source of truth for the build.",
            "5. Runs `make expansion-modern-toolchain-check` then boot-checks.",
            "runs `gba_playtest.py verify --policy behavior` against all three\n"
            "checkpoints (frames 0/60/120).",
            "eight performance-critical symbols are pinned to legacy IWRAM offsets.",
            "Adding these closes 17 prior cohort-unsatisfied symbols (the debug/aapcs\n"
            "unsatisfied set moves from 139 to 131).",
            "step three of the process installs the toolchain.",
        ):
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_object_count_claims(["doc.md"], root)
                self.assertEqual(findings, [], "unexpected finding for: %r" % phrase)

    def test_flagged_even_when_wrapped_across_a_line_break(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "compiles three handwritten\nassembly files to objects.\n")
            findings = check_docs.check_object_count_claims(["doc.md"], root)
            self.assertTrue(findings)
            # The reported line number is the line the number word itself
            # starts on (line 1), not the line the noun phrase concludes on.
            self.assertEqual(findings[0].line, 1)

    def test_flagged_even_inside_fenced_code_block(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md", "```text\nthe five save objects are compile-only\n```\n")
            stale_findings = check_docs.check_stale_phrases(["doc.md"], root)
            self.assertEqual(stale_findings, [])
            findings = check_docs.check_object_count_claims(["doc.md"], root)
            self.assertTrue(findings)

    def test_current_quickstart_has_no_spelled_object_count_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "quickstart.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "docs", "quickstart.md")
            ))
            findings = check_docs.check_object_count_claims(["quickstart.md"], root)
            self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# Fresh-review residual finding: docs/quickstart.md still carried "Three
# source files (`src/agb_sram.c`, `src/m4a.c`, `src/bmshop.c`) receive
# -fdata-sections" -- a bare "source files" noun (deliberately excluded
# from OBJECT_COUNT_SPELLED_RE's qualified-noun set so ordinary prose like
# "one source of truth" stays clean) paired with an explicit parenthetical
# enumeration of the actual paths. The prior round's own regression test
# suite locked this exact sentence in as a *required* zero-findings
# fixture (see the removed entry that used to live in
# test_ordinary_prose_and_unrelated_counts_do_not_false_positive above),
# which is precisely backwards: the checker should have caught this
# sentence, not exempted it. OBJECT_COUNT_SPELLED_ENUM_RE closes that
# escape; these fixtures prove the fail case is now caught, prove a
# colon-introduced enumeration is caught too, and prove the narrow scoping
# (no explicit enumeration attached) still leaves ordinary "one source of
# truth"/unenumerated prose untouched.
# ---------------------------------------------------------------------------

class SpelledObjectCountEnumerationClaimRegressionTests(unittest.TestCase):
    def test_real_old_quickstart_phrase_is_now_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md",
                  "Three source files (`src/agb_sram.c`, `src/m4a.c`, `src/bmshop.c`) receive\n"
                  "`-fdata-sections` so modern GCC emits the named sections.\n")
            findings = check_docs.check_object_count_claims(["doc.md"], root)
            self.assertTrue(findings, "expected the real removed quickstart sentence to be flagged")
            self.assertTrue(any("enumeration" in f.message for f in findings))

    def test_colon_introduced_enumeration_is_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md",
                  "Two files: `src/foo.c`, `src/bar.c` receive the override.\n")
            findings = check_docs.check_object_count_claims(["doc.md"], root)
            self.assertTrue(findings, "expected a colon-introduced enumeration to be flagged")

    def test_bare_file_word_without_source_qualifier_is_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "doc.md",
                  "Four files (`a.mk`, `b.mk`, `c.mk`, `d.mk`) are included here.\n")
            findings = check_docs.check_object_count_claims(["doc.md"], root)
            self.assertTrue(findings, "expected the bare 'files' + enumeration shape to be flagged")

    def test_one_source_of_truth_and_unenumerated_prose_do_not_false_positive(self):
        for phrase in (
            "This is one source of truth for the build.",
            "The three files are validated independently.",
            "all three boot checkpoints (frames 0/60/120) pass.",
            "5. Runs `make expansion-modern-toolchain-check` then boot-checks.",
            "step three of the process installs the toolchain.",
            "The source files that need this treatment receive `-fdata-sections`.",
            "modern.mk's \"IWRAM-placed symbols need per-symbol BSS sections\" block is "
            "the current source of truth for which sources carry the override.",
        ):
            with self.subTest(phrase=phrase), TempRepo() as repo:
                root = repo.root
                write(root, "doc.md", phrase + "\n")
                findings = check_docs.check_object_count_claims(["doc.md"], root)
                self.assertEqual(findings, [], "unexpected finding for: %r" % phrase)

    def test_current_quickstart_has_no_enumeration_findings(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "quickstart.md", check_docs.read_text(
                os.path.join(REAL_REPO_ROOT, "docs", "quickstart.md")
            ))
            findings = check_docs.check_object_count_claims(["quickstart.md"], root)
            self.assertEqual(findings, [],
                              "current quickstart.md should carry no explicit file-count "
                              "enumeration findings")


# ---------------------------------------------------------------------------
# Static Makefile-target database fixtures (never executes `make`)
# ---------------------------------------------------------------------------

class MakeTargetDatabaseTests(unittest.TestCase):
    def _write_makefile(self, root, content):
        write(root, "Makefile", content)

    def test_literal_target_found(self):
        with TempRepo() as repo:
            root = repo.root
            self._write_makefile(root, "all:\n\techo hi\n\nclean:\n\trm -rf build\n")
            literal, patterns = check_docs.parse_make_targets(root)
            self.assertIn("all", literal)
            self.assertIn("clean", literal)

    def test_pattern_target_matches(self):
        with TempRepo() as repo:
            root = repo.root
            self._write_makefile(root, "%.gba: %.elf\n\techo build\n")
            literal, patterns = check_docs.parse_make_targets(root)
            self.assertTrue(check_docs.make_target_exists("fireemblem8.gba", literal, patterns))

    def test_unknown_target_not_found(self):
        with TempRepo() as repo:
            root = repo.root
            self._write_makefile(root, "all:\n\techo hi\n")
            literal, patterns = check_docs.parse_make_targets(root)
            self.assertFalse(check_docs.make_target_exists("totally-made-up-target", literal, patterns))

    def test_include_graph_is_followed(self):
        with TempRepo() as repo:
            root = repo.root
            self._write_makefile(root, "include extra.mk\nall:\n\techo hi\n")
            write(root, "extra.mk", "extra-target:\n\techo extra\n")
            literal, patterns = check_docs.parse_make_targets(root)
            self.assertIn("extra-target", literal)

    def test_recipe_lines_are_never_parsed_as_targets(self):
        with TempRepo() as repo:
            root = repo.root
            # A recipe line containing a colon must never be mistaken for a rule.
            self._write_makefile(root, "all:\n\techo 'note: this looks like a target: but is not'\n")
            literal, patterns = check_docs.parse_make_targets(root)
            self.assertNotIn("this looks like a target", literal)

    def test_makefile_is_never_executed(self):
        """A recipe that would fail/mutate if actually run must not matter
        to target discovery, proving the parser never invokes `make`."""
        with TempRepo() as repo:
            root = repo.root
            self._write_makefile(root, "all:\n\texit 1\n\ttouch should-not-exist\n")
            literal, patterns = check_docs.parse_make_targets(root)
            self.assertIn("all", literal)
            self.assertFalse(os.path.exists(os.path.join(root, "should-not-exist")))


class MakeInvocationExtractionTests(unittest.TestCase):
    def test_bare_make_detected(self):
        text = "```bash\nmake\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertIn((True, None), results)

    def test_target_extracted_from_fenced_block(self):
        text = "```bash\nmake expansion-modern-toolchain-check\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertIn((False, "expansion-modern-toolchain-check"), results)

    def test_target_extracted_from_inline_code(self):
        text = "Run `make legacy` for the archival lane.\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertIn((False, "legacy"), results)

    def test_var_assignment_skipped_to_find_real_target(self):
        text = "```bash\nmake expansion-modern-elf MODERN_CONFIG=release MODERN_ABI=aapcs\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertIn((False, "expansion-modern-elf"), results)

    def test_make_colon_error_message_prose_ignored(self):
        text = "`make: *** No rule to make target 'x'.  Stop.`\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_placeholder_target_skipped(self):
        text = "`make -n <target>`\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_directory_redirect_skipped(self):
        text = "`make -C gcc`\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_trailing_shell_comment_does_not_leak_into_target(self):
        text = "```bash\nmake                # equivalent to: make all\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertIn((True, None), results)
        self.assertNotIn((False, "#"), results)

    def test_plain_prose_make_not_matched(self):
        text = "Make sure you run the tests before you make a change.\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_multiple_targets_all_yielded_not_just_the_first(self):
        # Regression for issue #17 finding 11: previously only the first
        # literal target token was ever inspected (via an early `break`),
        # so "make all nonexistent-target" silently ignored the second,
        # nonexistent target entirely. Both must now be yielded so a
        # downstream check_make_targets pass can flag the bad one even
        # though the first token is a real target.
        text = "```bash\nmake all nonexistent-target\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertIn((False, "all"), results)
        self.assertIn((False, "nonexistent-target"), results)
        self.assertEqual(len(results), 2)

    def test_multiple_legitimate_targets_all_pass_downstream_check(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "Makefile", "all:\n\techo hi\nclean:\n\techo bye\n")
            write(root, "doc.md", "```bash\nmake all clean\n```\n")
            literal, patterns = check_docs.parse_make_targets(root)
            findings = check_docs.check_make_targets(["doc.md"], root, literal, patterns)
            self.assertEqual(findings, [])

    def test_second_of_two_targets_is_flagged_by_downstream_check(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "Makefile", "all:\n\techo hi\n")
            write(root, "doc.md", "```bash\nmake all nonexistent-target\n```\n")
            literal, patterns = check_docs.parse_make_targets(root)
            findings = check_docs.check_make_targets(["doc.md"], root, literal, patterns)
            self.assertTrue(any("nonexistent-target" in f.message for f in findings), findings)

    def test_jobs_flag_and_its_value_token_skipped_target_still_found(self):
        text = "```bash\nmake -j 4 expansion-modern-toolchain-check\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertIn((False, "expansion-modern-toolchain-check"), results)
        self.assertNotIn((False, "4"), results)

    def test_file_redirect_flag_skips_whole_invocation(self):
        text = "```bash\nmake -f other.mk some-target\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_attached_file_redirect_flag_skips_whole_invocation(self):
        text = "```bash\nmake --file=other.mk some-target\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_attached_directory_long_form_redirect_flag_skips_whole_invocation(self):
        text = "```bash\nmake --directory=subdir some-target\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_attached_makefile_long_form_redirect_flag_skips_whole_invocation(self):
        text = "```bash\nmake --makefile=other.mk some-target\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_short_option_attached_file_redirect_flag_skips_whole_invocation(self):
        # Regression for the fresh code-review finding: `-fFILE` (attached,
        # no space/`=`) is just as legal to GNU make as `-f FILE`, but the
        # attached-flag detector previously only recognized the `--long=`
        # form, so `-fother.mk` fell through to the generic "starts with
        # `-`" branch and `some-target` was wrongly validated against this
        # repository's own Makefile graph instead of being skipped.
        text = "```bash\nmake -fother.mk some-target\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_short_option_attached_directory_redirect_flag_skips_whole_invocation(self):
        text = "```bash\nmake -Csubdir some-target\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_dangling_file_flag_alone_skips_invocation(self):
        # No filename token at all still fails closed (skip, never
        # validated) exactly like every other redirect form -- consistent
        # with the pre-existing `make -C` (no arg) behavior below.
        text = "`make -f`\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_dangling_directory_flag_alone_skips_invocation(self):
        text = "`make -C`\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertEqual(results, [])

    def test_jobs_short_attached_flag_not_mistaken_for_redirect(self):
        # `-j2` (attached short form of `-j`) must NOT be treated as a
        # Makefile/directory redirect -- only `-C`/`-f` get that
        # treatment -- so both real target tokens that follow are still
        # extracted and can be validated/flagged downstream.
        text = "```bash\nmake -j2 all nonexistent-target\n```\n"
        results = list(check_docs.extract_make_invocations(text))
        self.assertIn((False, "all"), results)
        self.assertIn((False, "nonexistent-target"), results)
        self.assertEqual(len(results), 2)


class CheckMakeTargetsIntegrationTests(unittest.TestCase):
    def test_stale_target_flagged(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "Makefile", "all:\n\techo hi\n")
            write(root, "doc.md", "```bash\nmake this-target-does-not-exist\n```\n")
            literal, patterns = check_docs.parse_make_targets(root)
            findings = check_docs.check_make_targets(["doc.md"], root, literal, patterns)
            self.assertTrue(findings)

    def test_known_target_passes(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "Makefile", "all:\n\techo hi\n")
            write(root, "doc.md", "```bash\nmake all\n```\n")
            literal, patterns = check_docs.parse_make_targets(root)
            findings = check_docs.check_make_targets(["doc.md"], root, literal, patterns)
            self.assertEqual(findings, [])

    def test_attached_file_redirect_never_validated_against_wrong_graph(self):
        # Regression for the fresh code-review finding: an external
        # Makefile target reachable only via `-fFILE` (attached) must
        # never be checked against *this* repository's root Makefile
        # graph. `external-only-target` does not exist in the root
        # Makefile below, but the whole invocation must still be skipped
        # rather than flagged, because it is documented as targeting a
        # different Makefile entirely.
        with TempRepo() as repo:
            root = repo.root
            write(root, "Makefile", "all:\n\techo hi\n")
            write(root, "doc.md", "```bash\nmake -fother.mk external-only-target\n```\n")
            literal, patterns = check_docs.parse_make_targets(root)
            findings = check_docs.check_make_targets(["doc.md"], root, literal, patterns)
            self.assertEqual(findings, [])

    def test_attached_directory_redirect_never_validated_against_wrong_graph(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "Makefile", "all:\n\techo hi\n")
            write(root, "doc.md", "```bash\nmake -Csubdir external-only-target\n```\n")
            literal, patterns = check_docs.parse_make_targets(root)
            findings = check_docs.check_make_targets(["doc.md"], root, literal, patterns)
            self.assertEqual(findings, [])

    def test_j2_attached_flag_still_flags_nonexistent_second_target(self):
        # Companion of the above: proves the fix does not overreach into
        # silencing *every* command-with-attached-short-flag -- `-j2` is
        # not a redirect flag, so a genuinely unknown target after it
        # must still be caught.
        with TempRepo() as repo:
            root = repo.root
            write(root, "Makefile", "all:\n\techo hi\n")
            write(root, "doc.md", "```bash\nmake -j2 all nonexistent-target\n```\n")
            literal, patterns = check_docs.parse_make_targets(root)
            findings = check_docs.check_make_targets(["doc.md"], root, literal, patterns)
            self.assertTrue(any("nonexistent-target" in f.message for f in findings), findings)


# ---------------------------------------------------------------------------
# Safe command runner fixtures: success, failure, and network/ROM rejection
# ---------------------------------------------------------------------------

class SafeCommandRunnerTests(unittest.TestCase):
    def test_help_invocation_is_safe(self):
        self.assertTrue(check_docs.is_command_safe([sys.executable, CHECK_DOCS_PATH, "--help"]))

    def test_network_tool_rejected(self):
        self.assertFalse(check_docs.is_command_safe(["curl", "https://example.com"]))

    def test_pip_install_rejected(self):
        self.assertFalse(check_docs.is_command_safe(["pip", "install", "something"]))

    def test_upstream_port_fetch_rejected(self):
        self.assertFalse(check_docs.is_command_safe(
            [sys.executable, "-m", "scripts.upstream_port", "fetch"]
        ))

    def test_upstream_port_verify_rejected(self):
        self.assertFalse(check_docs.is_command_safe(
            [sys.executable, "-m", "scripts.upstream_port", "verify"]
        ))

    def test_bare_make_all_rejected(self):
        self.assertFalse(check_docs.is_command_safe(["make", "all"]))
        self.assertFalse(check_docs.is_command_safe(["make", "fireemblem8.gba"]))

    def test_quickstart_help_runs_successfully(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        ok, message = check_docs.run_safe_example(
            "quickstart-help",
            [os.path.join(root, "scripts", "quickstart.sh"), "--help"],
            root,
        )
        self.assertTrue(ok, message)

    def test_check_docs_help_runs_successfully(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        ok, message = check_docs.run_safe_example(
            "check-docs-help", [sys.executable, CHECK_DOCS_PATH, "--help"], root,
        )
        self.assertTrue(ok, message)

    def test_unsafe_argv_is_refused_even_if_passed_to_run_safe_example(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        ok, message = check_docs.run_safe_example("curl-attempt", ["curl", "https://example.com"], root)
        self.assertFalse(ok)
        self.assertIn("refused", message)

    def test_failing_command_reports_failure(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        ok, message = check_docs.run_safe_example(
            "check-docs-bad-flag",
            [sys.executable, CHECK_DOCS_PATH, "--not-a-real-flag"],
            root,
        )
        self.assertFalse(ok)

    def test_bare_quickstart_with_no_arguments_is_unsafe(self):
        # Regression for issue #17 finding 12: a bare `./scripts/quickstart.sh`
        # invocation (no arguments at all) is a real installer/build/
        # network-capable invocation, not a help request, and must never
        # be judged safe.
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        quickstart = os.path.join(root, "scripts", "quickstart.sh")
        self.assertFalse(check_docs.is_command_safe([quickstart]))

    def test_quickstart_help_with_extra_positional_argument_is_unsafe(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        quickstart = os.path.join(root, "scripts", "quickstart.sh")
        self.assertFalse(check_docs.is_command_safe([quickstart, "--help", "extra-arg"]))

    def test_quickstart_help_combined_with_build_flag_is_unsafe(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        quickstart = os.path.join(root, "scripts", "quickstart.sh")
        self.assertFalse(check_docs.is_command_safe([quickstart, "--rom", "--help"]))

    def test_quickstart_install_flag_alone_is_unsafe(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        quickstart = os.path.join(root, "scripts", "quickstart.sh")
        self.assertFalse(check_docs.is_command_safe([quickstart, "--refresh-agbcc"]))

    def test_quickstart_dash_h_alone_is_safe(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        quickstart = os.path.join(root, "scripts", "quickstart.sh")
        self.assertTrue(check_docs.is_command_safe([quickstart, "-h"]))

    def test_bare_quickstart_rejected_by_run_safe_example_with_zero_subprocess_calls(self):
        # Adversarial proof that the rejection happens *before* any
        # subprocess is spawned: patch subprocess.run to explode if
        # called at all, then confirm run_safe_example still reports
        # refusal (not a crash from the patched subprocess.run).
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        quickstart = os.path.join(root, "scripts", "quickstart.sh")
        with mock.patch.object(check_docs.subprocess, "run") as run_mock:
            run_mock.side_effect = AssertionError(
                "subprocess.run must never be called for an unsafe example"
            )
            ok, message = check_docs.run_safe_example("quickstart-bare", [quickstart], root)
        self.assertFalse(ok)
        self.assertIn("refused", message)
        run_mock.assert_not_called()

    def test_quickstart_extra_arg_rejected_by_run_safe_example_with_zero_subprocess_calls(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        quickstart = os.path.join(root, "scripts", "quickstart.sh")
        with mock.patch.object(check_docs.subprocess, "run") as run_mock:
            run_mock.side_effect = AssertionError(
                "subprocess.run must never be called for an unsafe example"
            )
            ok, message = check_docs.run_safe_example(
                "quickstart-help-plus-arg", [quickstart, "--help", "extra"], root,
            )
        self.assertFalse(ok)
        run_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Discovery + end-to-end CLI smoke test
# ---------------------------------------------------------------------------

class DiscoveryTests(unittest.TestCase):
    def test_tracked_and_untracked_markdown_both_found_ignored_excluded(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "tracked.md", "# T\n")
            git(root, "add", "tracked.md")
            git(root, "commit", "-q", "-m", "init")
            write(root, "untracked.md", "# U\n")
            write(root, ".gitignore", "ignored.md\n")
            write(root, "ignored.md", "# I\n")
            files = check_docs.discover_markdown_files(root)
            self.assertIn("tracked.md", files)
            self.assertIn("untracked.md", files)
            self.assertNotIn("ignored.md", files)

    # -----------------------------------------------------------------
    # Second final-verifier residual finding #2: discover_markdown_files()
    # previously used a `git ls-files -- '*.md'` pathspec, so a real
    # Markdown file using any other recognized extension (`.markdown`,
    # `.mdown`, `.mkd`) -- or an uppercase variant of any recognized
    # extension -- was silently invisible to every check keyed off "the
    # set of Markdown files" (inventory coverage, link/anchor resolution,
    # external-URL registry coverage, stale-phrase/object-count scanning).
    # These fixtures prove the fixed, full-listing-plus-Python-filter
    # implementation actually recognizes the full documented set, still
    # respects tracked/untracked/ignored semantics for each one, still
    # excludes a genuinely unrecognized extension, and returns a stable
    # sorted order even with a space in a path.
    # -----------------------------------------------------------------

    def test_tracked_alternate_extensions_all_discovered(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.markdown", "# A\n")
            write(root, "b.mdown", "# B\n")
            write(root, "c.mkd", "# C\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "init")
            files = check_docs.discover_markdown_files(root)
            self.assertIn("a.markdown", files)
            self.assertIn("b.mdown", files)
            self.assertIn("c.mkd", files)

    def test_untracked_alternate_extensions_discovered(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "tracked.md", "# T\n")
            git(root, "add", "tracked.md")
            git(root, "commit", "-q", "-m", "init")
            write(root, "untracked.markdown", "# U\n")
            files = check_docs.discover_markdown_files(root)
            self.assertIn("untracked.markdown", files)

    def test_uppercase_recognized_extension_discovered(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "UPPER.MD", "# U\n")
            write(root, "Mixed.Markdown", "# M\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "init")
            files = check_docs.discover_markdown_files(root)
            self.assertIn("UPPER.MD", files)
            self.assertIn("Mixed.Markdown", files)

    def test_ignored_alternate_extension_excluded(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "tracked.md", "# T\n")
            git(root, "add", "tracked.md")
            git(root, "commit", "-q", "-m", "init")
            write(root, ".gitignore", "ignored.mkd\n")
            write(root, "ignored.mkd", "# I\n")
            files = check_docs.discover_markdown_files(root)
            self.assertNotIn("ignored.mkd", files)

    def test_unrecognized_extension_not_discovered(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "tracked.md", "# T\n")
            write(root, "notes.txt", "plain text\n")
            write(root, "weird.mdx", "# not recognized\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "init")
            files = check_docs.discover_markdown_files(root)
            self.assertIn("tracked.md", files)
            self.assertNotIn("notes.txt", files)
            self.assertNotIn("weird.mdx", files)

    def test_stable_sorted_order_including_space_path(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "z.md", "# Z\n")
            write(root, "docs/a doc.markdown", "# A doc\n")
            write(root, "a.mkd", "# A\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "init")
            files = check_docs.discover_markdown_files(root)
            self.assertEqual(files, sorted(files))
            self.assertIn("docs/a doc.markdown", files)


class RecognizedExtensionInventoryTests(unittest.TestCase):
    """Inventory exact-coverage (missing/extra) applied to alternate
    recognized Markdown extensions, not just `.md` -- proving
    check_inventory_coverage() is keyed off discover_markdown_files()'s
    full recognized set, not a `.md`-only assumption baked into the
    coverage check itself."""

    def _write_inventory(self, root, entries_block):
        content = (
            "# Inventory\n\n"
            + check_docs.INVENTORY_BEGIN + "\n"
            + entries_block + "\n"
            + check_docs.INVENTORY_END + "\n"
        )
        write(root, check_docs.INVENTORY_PATH, content)

    def test_missing_entry_detected_for_alternate_extension(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.md", "# A\n")
            write(root, "b.markdown", "# B\n")
            self._write_inventory(root, "- a.md | alice | current | test doc\n"
                                         "- " + check_docs.INVENTORY_PATH + " | alice | current | inventory")
            entries, _ = check_docs.parse_inventory(root)
            files = check_docs.discover_markdown_files(root)
            findings = check_docs.check_inventory_coverage(root, files, entries)
            messages = [f.message for f in findings]
            self.assertTrue(any("b.markdown" in m and "missing" in m for m in messages))

    def test_extra_entry_detected_for_nonexistent_alternate_extension(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.md", "# A\n")
            self._write_inventory(root, "- a.md | alice | current | test doc\n"
                                         "- ghost.mkd | alice | current | does not exist\n"
                                         "- " + check_docs.INVENTORY_PATH + " | alice | current | inventory")
            entries, _ = check_docs.parse_inventory(root)
            files = check_docs.discover_markdown_files(root)
            findings = check_docs.check_inventory_coverage(root, files, entries)
            messages = [f.message for f in findings]
            self.assertTrue(any("ghost.mkd" in m for m in messages))

    def test_alternate_extension_with_inventory_entry_passes(self):
        with TempRepo() as repo:
            root = repo.root
            write(root, "a.mdown", "# A\n")
            self._write_inventory(root, "- a.mdown | alice | current | test doc\n"
                                         "- " + check_docs.INVENTORY_PATH + " | alice | current | inventory")
            entries, errors = check_docs.parse_inventory(root)
            self.assertEqual(errors, [])
            files = check_docs.discover_markdown_files(root)
            findings = check_docs.check_inventory_coverage(root, files, entries)
            self.assertEqual(findings, [])


class CliSmokeTests(unittest.TestCase):
    def test_help_flag_exits_zero(self):
        result = subprocess.run(
            [sys.executable, CHECK_DOCS_PATH, "--help"], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())

    def test_real_repository_passes_check(self):
        root = check_docs.get_repo_root(os.path.dirname(CHECK_DOCS_PATH))
        result = subprocess.run(
            [sys.executable, CHECK_DOCS_PATH, "--check"], cwd=root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
