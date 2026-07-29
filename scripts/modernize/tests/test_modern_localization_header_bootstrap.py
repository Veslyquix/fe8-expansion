"""Issue #18 sprint-3 verifier-blocker regression test.

A clean/cold checkout's first modern build must never intermittently fail
with::

    make: *** No rule to make target 'expansion_msg_ids.h', needed by
    'build/expansion-modern/<config>/aapcs/src/debugtools_registry.o'.  Stop.

Root cause (see modern.mk's own comment above the fix, next to
``MODERN_LOCALIZATION_MSG_IDS_H_BASENAME``): several modern-only C sources
(``src/uiconfig.c``, ``src/save_compat_menu.c``, ``src/debugtools_registry.c``,
``src/expansion_language_menu.c``) ``#include "expansion_msg_ids.h"`` bare,
resolved only through modern.mk's own extra ``-I`` search path onto the
*generated* ``build/expansion-localization/generated/expansion_msg_ids.h``.
On a cold build that header does not exist yet, so GCC's own ``-MM -MG``
generated-header probe (used by the ``.headers.d`` bootstrap for exactly
this kind of not-yet-generated, non-INCBIN header -- see modern.mk's
``MODERN_ALL_C_HEADER_DEPS`` comment) cannot resolve it through that ``-I``
path at all: it records the bare literal ``expansion_msg_ids.h`` instead of
the header's real, rule-backed path. That bare name has no matching rule,
so a build that reaches this via any of ``MODERN_ALL_SOURCE_GOALS``
(``expansion-modern-elf``/``-all``/``-rom``/...) fails with "No rule to
make target" -- intermittently, depending only on whether some earlier,
unrelated target already caused the real header to exist on disk (e.g. a
leftover ``build/`` directory), which is exactly why this was only ever
caught by CI/local runs that happened to start from a *dirty* cache.

These tests always start from a genuinely cold state (the generated
localization directory removed, never relying on any pre-existing
``build/`` cache) and cover both supported ``MODERN_CONFIG`` values,
directly reproducing the reported clean-build failure mode with two of
its real, in-repo direct consumers: ``src/debugtools_registry.c`` (the
debug-tools registry) and ``src/expansion_language_menu.c`` (the
first-start language selector / settings submenu). They exercise the
*real* repository sources and the *real* localization generator (never a
synthetic fixture tree), because the bug is specifically about how those
two interact through modern.mk's own generated-header wiring.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

# The one repository-relative directory this bug is about. Always a
# gitignored build/ subdirectory (see .gitignore's blanket "build/" entry)
# -- never a committed source path -- so removing it never touches or
# resets any source file.
LOCALIZATION_ROOT = ROOT / "build" / "expansion-localization"
LOCALIZATION_HEADER = LOCALIZATION_ROOT / "generated" / "expansion_msg_ids.h"

# The direct, real (non-fixture) generated-header consumers this sprint's
# regression must cover, per the task contract: the debug-tools registry
# and the first-start language menu.
CONSUMER_SOURCES = (
    "src/debugtools_registry.c",
    "src/expansion_language_menu.c",
)

MODERN_CONFIGS = ("debug", "release")


def _toolchain_available():
    return bool(
        shutil.which("arm-none-eabi-gcc")
        and shutil.which("arm-none-eabi-objdump")
        and shutil.which("arm-none-eabi-ld")
    )


class ModernLocalizationHeaderBootstrapTests(unittest.TestCase):

    def setUp(self):
        # Never depend on a stale build/ cache left over from a previous
        # local invocation or another test in this suite -- the whole
        # point of this regression is a truly cold start, where
        # expansion_msg_ids.h (and its sibling generated files) does not
        # exist anywhere yet.
        self._clean_localization_output()
        self.addCleanup(self._clean_localization_output)

    @staticmethod
    def _clean_localization_output():
        if LOCALIZATION_ROOT.is_dir():
            shutil.rmtree(LOCALIZATION_ROOT)

    def _make(self, *args):
        return subprocess.run(
            ["make", "--no-print-directory", *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def _assert_no_missing_rule(self, stdout):
        self.assertNotIn(
            "No rule to make target", stdout,
            "clean build must never hit an unresolvable generated-header "
            "prerequisite",
        )

    def _assert_generation_precedes_consumer(self, stdout, source_rel):
        gen_idx = stdout.find("scripts.localization.cli generate")
        self.assertNotEqual(
            gen_idx, -1,
            f"localization header generation step missing from output "
            f"(checking ordering for {source_rel})",
        )
        consumer_idx = stdout.find(f'-c "{source_rel}"')
        self.assertNotEqual(
            consumer_idx, -1,
            f"compile step for {source_rel} missing from output",
        )
        self.assertLess(
            gen_idx, consumer_idx,
            f"{source_rel} must never be compiled before "
            f"expansion_msg_ids.h is generated",
        )

    # -- Fast, deterministic dry-run coverage (both configs) -----------------
    #
    # `make -n` still triggers modern.mk's real remake-restart of the
    # `.headers.d` bootstrap makefiles (see modern.mk's own comment on
    # this), which is exactly where the bare, unresolvable
    # "expansion_msg_ids.h" prerequisite used to be introduced -- so a
    # dry run genuinely reproduces (or, once fixed, genuinely rules out)
    # the reported failure without paying for a full 456-object compile.

    def _run_dry_run(self, config):
        with tempfile.TemporaryDirectory() as tmp:
            iso_root = Path(tmp) / "iso-build"
            return self._make(
                "-n", "expansion-modern-elf",
                f"MODERN_CONFIG={config}",
                f"MODERN_BUILD_ROOT={iso_root}",
            )

    def test_debug_cold_dry_run_orders_header_before_consumers(self):
        result = self._run_dry_run("debug")
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        self._assert_no_missing_rule(result.stdout)
        for source in CONSUMER_SOURCES:
            self._assert_generation_precedes_consumer(result.stdout, source)

    def test_release_cold_dry_run_orders_header_before_consumers(self):
        result = self._run_dry_run("release")
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        self._assert_no_missing_rule(result.stdout)
        for source in CONSUMER_SOURCES:
            self._assert_generation_precedes_consumer(result.stdout, source)

    # -- Real, isolated-output build coverage (both configs) -----------------
    #
    # A dry run alone cannot prove the recipe actually executes correctly
    # end to end (e.g. a genuinely broken generator recipe would still
    # "order" correctly in -n output). These run the real toolchain
    # against the real repository sources -- never a synthetic fixture,
    # since this bug is specifically about how the real generated header
    # and these real consumers interact -- with build output isolated to
    # a throwaway directory (MODERN_BUILD_ROOT) so no repository-tracked
    # state or other tests' cached objects are read or disturbed.

    def _run_real_isolated_build(self, config):
        with tempfile.TemporaryDirectory() as tmp:
            iso_root = Path(tmp) / "iso-build"
            result = self._make(
                "expansion-modern-elf",
                f"MODERN_CONFIG={config}",
                f"MODERN_BUILD_ROOT={iso_root}",
            )
            self.assertEqual(result.returncode, 0, result.stdout[-3000:])
            self._assert_no_missing_rule(result.stdout)
            self.assertTrue(
                LOCALIZATION_HEADER.is_file(),
                "expansion_msg_ids.h was not actually generated",
            )
            out_dir = iso_root / config / "aapcs" / "src"
            for source in CONSUMER_SOURCES:
                obj = out_dir / (Path(source).name[:-2] + ".o")
                self.assertTrue(
                    obj.is_file(),
                    f"{obj} was not produced by the real isolated build",
                )

    def test_debug_cold_real_isolated_build_succeeds(self):
        if not _toolchain_available():
            self.skipTest("modern toolchain not available")
        self._run_real_isolated_build("debug")

    def test_release_cold_real_isolated_build_succeeds(self):
        if not _toolchain_available():
            self.skipTest("modern toolchain not available")
        self._run_real_isolated_build("release")


class ModernLocalizationGenerationParallelSafetyTests(unittest.TestCase):
    """A second, distinct clean-build hazard found while fixing the
    "No rule to make target 'expansion_msg_ids.h'" regression above: the
    single recipe that produces all three generated localization outputs
    (expansion_locale_catalog.c, expansion_msg_ids.h, budget.json) used to
    be declared as a plain, non-grouped multi-target rule. GNU Make treats
    every target of such a rule as an independent goal with its own copy
    of the recipe; since sprint 3 gives two *different* outputs of that
    same rule independent real consumers (every ordinary modern object
    now depends on expansion_msg_ids.h, while the generated-catalog object
    depends on expansion_locale_catalog.c), a real "-j>1" clean build can
    -- and, instrumented, empirically does -- invoke the generator recipe
    concurrently from two different PIDs. scripts/localization/generate.py
    writes each output file in place (no atomic temp-file-plus-rename), so
    concurrent invocations are a genuine torn/corrupted-write hazard, not
    just wasted duplicate work.

    The fix is GNU Make 4.3's grouped "&:" target syntax (already relied
    on elsewhere in this codebase's own toolchain baseline -- see the
    FETSATOOL comment's "isolated GNU Make 4.3 reproduction" above this
    rule in modern.mk), which guarantees the recipe runs at most once per
    invocation regardless of how many of its outputs are needed. This is a
    fast, deterministic *static* guard against ever silently reverting to
    the unsafe plain multi-target form; the dynamic race itself was
    confirmed manually (instrumented recipe, "-j16", two distinct PIDs
    both inside the recipe body at once) rather than asserted here, since
    reliably forcing a many-millisecond-wide scheduling race in a fast
    unit test would itself be flaky.
    """

    MODERN_MK = (Path(__file__).resolve().parents[3] / "modern.mk").read_text(
        encoding="utf-8"
    )

    def test_localization_generation_uses_grouped_target(self):
        self.assertIn(
            "$(MODERN_LOCALIZATION_CATALOG_C) $(MODERN_LOCALIZATION_MSG_IDS_H) "
            "$(MODERN_LOCALIZATION_BUDGET_JSON) &: FORCE_MODERN_LOCALIZATION",
            self.MODERN_MK,
            "localization generation must be a GNU Make 4.3 grouped '&:' "
            "target -- a plain multi-target rule lets GNU Make invoke the "
            "shared generator recipe concurrently from independent goals "
            "under a parallel (-j>1) build",
        )


if __name__ == "__main__":
    unittest.main()
