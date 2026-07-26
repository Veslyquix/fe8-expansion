import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

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
