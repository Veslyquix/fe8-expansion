"""Documentation/assertion regression tests for release.mk's and the
release docs' Make-vs-CLI exit-code claims (fresh-review remediation).

GNU Make's own process exit status, for *any* failed recipe, is always 2
-- it never preserves/forwards the recipe's actual non-zero exit code.
This module (a) proves that fact empirically, both in the abstract (a
synthetic, repository-independent Makefile) and against this real
repository's actual, currently-BLOCKED `make release-check-require-
eligible` invocation (whose underlying CLI recipe is expected to, and
does, exit 1 -- see docs/release_process.md's "Exit code contract"), and
(b) statically guards against release.mk's/the release docs' comments
ever again claiming that a *Make target itself* (as opposed to the
underlying CLI, invoked directly) exits 1 or 3.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def _make(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["make", *args], cwd=str(ROOT), capture_output=True, text=True)


@unittest.skipUnless(shutil.which("make"), "make not available on PATH")
class MakeWrapperExitCodeTests(unittest.TestCase):
    """Empirical (never assumed) proof of GNU Make's own recipe-failure
    exit-code convention."""

    def test_gnu_make_itself_always_reports_2_for_any_failed_recipe(self):
        """A minimal synthetic Makefile, entirely independent of this
        repository's own tooling, proving GNU Make's own universal
        behavior: a non-zero recipe exit (1, 3, or otherwise) is always
        reported by `make` itself as exit 2, never the recipe's own
        code."""
        with tempfile.TemporaryDirectory() as tmp:
            makefile = Path(tmp) / "Makefile"
            makefile.write_text("t1:\n\texit 1\nt3:\n\texit 3\nt5:\n\texit 5\n", encoding="utf-8")
            for target in ("t1", "t3", "t5"):
                result = subprocess.run(
                    ["make", "-f", str(makefile), target], cwd=tmp, capture_output=True, text=True,
                )
                self.assertEqual(
                    result.returncode, 2,
                    f"expected make's own exit code to always be 2 for a failed "
                    f"recipe (target {target!r}), got {result.returncode}",
                )

    def test_real_require_eligible_target_exits_2_through_make_not_1(self):
        """The real, currently-BLOCKED candidate's `--require-eligible`
        gate: the underlying CLI recipe itself exits 1
        (`EXIT_NOT_ELIGIBLE` -- see scripts/release_rehearsal/cli.py), but
        `make release-check-require-eligible` itself must be observed to
        exit 2, never 1 (see release.mk's own corrected comments)."""
        result = _make("release-check-require-eligible")
        self.assertEqual(
            result.returncode, 2,
            f"expected 'make release-check-require-eligible' to exit 2 (GNU "
            f"Make's own recipe-failure code) while the candidate is blocked, "
            f"got {result.returncode}. stderr tail: {result.stderr[-500:]!r}",
        )
        # The underlying CLI's own literal exit-1 statement is still visible
        # in the recipe's own stderr output -- proof the CLI itself did
        # exit 1 even though `make` reports 2.
        self.assertIn("exit 1", result.stderr)

    def test_real_expect_blocked_target_exits_0_while_truly_blocked(self):
        """The "healthy" (still-blocked, as expected) case must still be
        observed as exit 0 through `make` -- Make's exit-collapsing-to-2
        behavior only ever applies to a *failed* recipe; a successful one
        (exit 0) is always reported faithfully, with no code change
        required to prove it."""
        result = _make("release-check-expect-blocked")
        self.assertEqual(result.returncode, 0, msg=result.stderr[-500:])


class ReleaseMkAndDocsExitCodeClaimsTests(unittest.TestCase):
    """Static guard: release.mk's header comments and the release docs
    must never again claim that a *Make target itself* exits 1 or 3 --
    only the underlying CLI, invoked directly, does."""

    def _text(self, relpath: str) -> str:
        return (ROOT / relpath).read_text(encoding="utf-8")

    def test_release_mk_no_longer_claims_a_bare_target_exit_1(self):
        text = self._text("release.mk")
        self.assertNotIn("Exits 1 (not 0) while BLOCKED.", text)

    def test_release_mk_no_longer_claims_a_bare_target_exit_3_without_qualification(self):
        text = self._text("release.mk")
        self.assertNotIn(
            "they exit 0 ONLY if the candidate's status is exactly",
            text,
        )

    def test_release_mk_documents_make_exit_2_collapsing_behavior(self):
        text = self._text("release.mk")
        self.assertIn("always\n# reports the *target*'s own exit status as exit code 2", text)
        self.assertIn("The CLI itself exits 1 while", text)
        self.assertIn("`make` itself reports exit 2\n# (not 3)", text)

    def test_release_process_doc_documents_make_exit_2_collapsing_behavior(self):
        text = self._text("docs/release_process.md")
        self.assertIn("GNU Make reports *any* failed recipe", text)
        self.assertIn(
            "so running these specific targets\n  through `make`",
            text,
        )

    def test_release_closure_candidate_doc_no_longer_claims_bare_make_exit_1(self):
        text = self._text("docs/release_closure_candidate.md")
        self.assertNotIn(
            "EXPECTED to exit\n# non-zero (1) while the candidate is blocked -- this is not a failure of",
            text,
        )
        self.assertIn('"exit=2", not "exit=1"', text)

    def test_no_release_doc_claims_a_make_target_itself_exits_1_or_3(self):
        """Sweep every release-process doc + release.mk for the specific,
        narrow, previously-wrong phrasing pattern this remediation fixed:
        a claim that running a target *through `make`* itself yields exit
        1 or 3. This deliberately does not forbid the substrings "exit 1"
        or "exit 3" outright (the underlying CLI's own 0/1/2/3 contract,
        documented correctly, legitimately uses them) -- only the exact
        previously-incorrect phrasings themselves."""
        offending_phrases = (
            "Exits 1 (not 0) while BLOCKED.",
            "EXPECTED to exit\n# non-zero (1) while the candidate is blocked -- this is not a failure of",
            "**These are intentionally expected to, and currently do, exit non-zero\n  (`1`) while the candidate is `blocked`.**",
        )
        for relpath in ("release.mk", "docs/release_process.md", "docs/release_closure_candidate.md"):
            text = self._text(relpath)
            for phrase in offending_phrases:
                self.assertNotIn(phrase, text, f"{relpath} still contains stale phrasing: {phrase!r}")


if __name__ == "__main__":
    unittest.main()
