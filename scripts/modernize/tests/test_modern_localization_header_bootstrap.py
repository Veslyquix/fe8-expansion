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

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

# The one repository-relative directory this bug is about. Always a
# gitignored build/ subdirectory (see .gitignore's blanket "build/" entry)
# -- never a committed source path -- so removing it never touches or
# resets any source file.
#
# Issue #18 sprint 5: this used to be a single hardcoded
# "build/expansion-localization" shared by every MODERN_BUILD_ROOT
# (default and the recursively-invoked multi-locale build alike) -- see
# modern.mk's own comment on MODERN_LOCALIZATION_ROOT for the real
# cross-process-tree race this caused. It is now keyed off
# MODERN_BUILD_ROOT (default "build/expansion-modern"), so this
# constant -- covering the *default* build root specifically -- moves in
# lockstep with modern.mk's own default. `_run_real_isolated_build` below
# derives its own build-root-specific header path per call instead of
# reusing this constant, exactly because its whole point is exercising a
# *different* MODERN_BUILD_ROOT each time.
LOCALIZATION_ROOT = ROOT / "build" / "expansion-modern" / "expansion-localization"
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
        # The multi-locale build root (issue #18 sprint 4's
        # expansion-modern-localization-runtime-multi-check) is a
        # completely separate MODERN_BUILD_ROOT with its own,
        # independent generated-localization copy since sprint 5's
        # config-specific-path fix -- clean it too so this suite never
        # depends on (or is polluted by) a previous multi-locale build.
        multi_root = ROOT / "build" / "expansion-modern-multi" / "expansion-localization"
        if multi_root.is_dir():
            shutil.rmtree(multi_root)

    def _make(self, *args, env=None):
        return subprocess.run(
            ["make", "--no-print-directory", *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env=env,
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
    #
    # The expected header path is derived from *this call's own*
    # iso_root (not the shared LOCALIZATION_ROOT/LOCALIZATION_HEADER
    # constants above) -- since sprint 5's config-specific-path fix,
    # MODERN_LOCALIZATION_ROOT lives under $(MODERN_BUILD_ROOT) itself,
    # so a caller-supplied MODERN_BUILD_ROOT override (exactly what this
    # isolated-build helper does) must be honored here too, or this test
    # would silently degrade into checking the wrong (unrelated, real
    # default-build-root) path instead of proving *this* isolated build
    # actually generated its own private copy.

    def _run_real_isolated_build(self, config):
        with tempfile.TemporaryDirectory() as tmp:
            iso_root = Path(tmp) / "iso-build"
            iso_header = iso_root / "expansion-localization" / "generated" / "expansion_msg_ids.h"
            result = self._make(
                "expansion-modern-elf",
                f"MODERN_CONFIG={config}",
                f"MODERN_BUILD_ROOT={iso_root}",
            )
            self.assertEqual(result.returncode, 0, result.stdout[-3000:])
            self._assert_no_missing_rule(result.stdout)
            self.assertTrue(
                iso_header.is_file(),
                "expansion_msg_ids.h was not actually generated under this "
                "isolated build's own MODERN_BUILD_ROOT",
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


def _libmgba_available():
    """Whether tools/gba-playtest/backend.c actually links against a real
    libmGBA on this host -- checked the *same* way gba_playtest.py's own
    build_backend() resolves it (a bare ``-lmgba`` fallback whenever
    ``pkg-config --cflags --libs mgba`` is unavailable/fails, e.g. this
    sprint's own dev container, which ships libmgba-dev's headers/.so but
    no mgba.pc), never a pkg-config-only probe that would wrongly report
    "unavailable" on hosts exactly like that one. Reuses gba_playtest.py's
    own real compiler-invocation logic directly (never a duplicated,
    potentially-drifting re-implementation of it) via a throwaway
    temp-directory build of the real backend.c."""
    sys.path.insert(0, str(ROOT / "tools" / "gba-playtest"))
    import gba_playtest as _gba_playtest  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="libmgba-probe-") as tmp:
        probe_binary = Path(tmp) / "gba_playtest_backend_probe"
        try:
            _gba_playtest.build_backend(probe_binary)
        except _gba_playtest.PlaytestError:
            return False
    return True


class ModernLocalizationMultiCheckColdCleanTests(unittest.TestCase):
    """Issue #18 sprint 5 contract item #1: a genuinely cold (no
    prebuilt/precached ``build/`` output anywhere, and *never* a manual
    ``make expansion-localization-generate``/``scripts.localization.cli
    generate`` run first) invocation of
    ``expansion-modern-localization-runtime-multi-check`` -- the target
    whose own recursive ``+$(MAKE) expansion-modern-rom
    MODERN_BUILD_ROOT=build/expansion-modern-multi ...`` sub-invocation
    was the concrete repro for the cross-process-tree generated-header
    race documented on modern.mk's own ``MODERN_LOCALIZATION_ROOT``
    comment -- must always succeed sequentially (deliberately never
    passed ``-j``/``MAKEFLAGS`` here: see modern.mk's own "Bugs found and
    fixed" note on ``-j`` parallelism, which remains a real, separate,
    documented hazard this specific regression does not attempt to
    reproduce or fix).

    Runs both ``MODERN_CONFIG`` values against a throwaway, isolated
    ``MODERN_BUILD_ROOT`` (never the real repository-tracked ``build/``
    tree, and never seeded with a prebuilt generated header) so this
    test is itself fully hermetic and safe to run alongside every other
    test in this module.
    """

    def _run_cold_multi_check(self, config):
        with tempfile.TemporaryDirectory() as tmp:
            iso_root = Path(tmp) / "iso-build"
            result = subprocess.run(
                [
                    "make", "--no-print-directory",
                    "expansion-modern-localization-runtime-multi-check",
                    f"MODERN_CONFIG={config}",
                    "MODERN_ABI=aapcs",
                    f"MODERN_BUILD_ROOT={iso_root}",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout[-4000:])
            self.assertNotIn(
                "No rule to make target", result.stdout,
                "cold expansion-modern-localization-runtime-multi-check "
                "must never hit an unresolvable generated-header "
                "prerequisite for either build root",
            )
            self.assertIn(
                "localization-runtime multi-check passed", result.stdout,
            )
            # This target's own recursive sub-make actually builds under
            # MODERN_LOCALE_MULTI_BUILD_ROOT (a "-multi" sibling of the
            # caller-supplied MODERN_BUILD_ROOT since this sprint's own
            # fix -- see modern.mk's own comment there), never the
            # caller's MODERN_BUILD_ROOT directly and never the real
            # repository-tracked default -- so this isolated build's own
            # generated header must exist under *that* derived path.
            iso_multi_root = iso_root.parent / (iso_root.name + "-multi")
            iso_header = (
                iso_multi_root / "expansion-localization" / "generated"
                / "expansion_msg_ids.h"
            )
            self.assertTrue(
                iso_header.is_file(),
                "expansion_msg_ids.h was not generated under this cold "
                "isolated multi-check build's own derived multi-locale "
                "build root",
            )

    def test_debug_cold_clean_multi_check_succeeds(self):
        if not _toolchain_available():
            self.skipTest("modern toolchain not available")
        if not _libmgba_available():
            self.skipTest("libmGBA (pkg-config mgba) not available")
        self._run_cold_multi_check("debug")

    def test_release_cold_clean_multi_check_succeeds(self):
        if not _toolchain_available():
            self.skipTest("modern toolchain not available")
        if not _libmgba_available():
            self.skipTest("libmGBA (pkg-config mgba) not available")
        self._run_cold_multi_check("release")


class ModernLocalizationHeaderFilterPortabilityTests(unittest.TestCase):
    """Issue #18 known-High fix: the ``.headers.d`` bootstrap recipe's
    bare-token filter used to run ``sed -E -i 's/.../' "$@.tmp"``. GNU
    sed's ``-i`` takes an *optional* backup-suffix argument (bare ``-i``
    means "no backup"); BSD/macOS sed's ``-i`` takes a *mandatory* one --
    an explicit ``-i ''`` is required for "no backup", and a bare ``-i``
    is either a hard usage error or silently consumes the very next token
    (here, the actual filter regex) as the backup suffix. Either way, the
    old recipe was GNU-sed-only and broke a supported host (macOS/
    Homebrew; see this Makefile's own Darwin-conditional ``$(SED)``
    definition used elsewhere in this codebase).

    The fix (see modern.mk's own comment directly above the recipe)
    drops ``-i`` entirely: the filtered stream is redirected to a second,
    per-target-unique temp file and atomically renamed over the real
    target, exactly like the pre-scan step immediately above it in the
    same recipe. Plain ``sed -E 's/.../' in > out`` (no ``-i``) is
    command-line identical on GNU and BSD/macOS sed.

    A source-level string check alone would accept a merely *reworded*
    but still GNU-only invocation (e.g. swapping flag order), so the
    primary coverage here is behavioral: these tests run the real,
    unmodified recipe through a real cold Linux build with a hostile,
    intentionally-strict fake ``sed`` shim placed first on ``PATH`` --
    one that hard-fails on any bare ``-i`` token exactly the way real
    BSD/macOS sed would misbehave on one -- and confirm the build still
    filters the bare ``expansion_msg_ids.h`` token correctly with that
    shim active. The static source assertion below is kept only as a
    cheap, fast *supplementary* guard against literally reintroducing
    ``sed ... -i`` on this recipe, never as the sole test.
    """

    MODERN_MK_PATH = Path(__file__).resolve().parents[3] / "modern.mk"
    MODERN_MK = MODERN_MK_PATH.read_text(encoding="utf-8")

    # The hostile fake-sed shim's own diagnostic string (see
    # _write_hostile_bsd_sed_shim below): if this ever appears in a
    # build's output, the recipe under test reached a real `sed -i`
    # invocation, which is exactly the portability landmine being
    # guarded against here.
    HOSTILE_SED_FAILURE_MARKER = (
        "fake-bsd-sed: -i: option requires an argument"
    )

    _HOSTILE_SED_SHIM_TEMPLATE = """#!/usr/bin/env bash
# Hostile BSD/macOS-like fake sed -- see
# ModernLocalizationHeaderFilterPortabilityTests. Real BSD/macOS sed
# requires an explicit (possibly empty) backup-suffix argument
# immediately after -i; a bare -i is either a hard usage error or
# silently consumes the very next token as that suffix. This shim
# always hard-fails on a bare -i so any recipe reaching it is proven to
# depend on GNU-only bare -i semantics.
for arg in "$@"; do
    if [ "$arg" = "-i" ]; then
        echo "HOSTILE_SED_FAILURE_MARKER_TOKEN" >&2
        exit 1
    fi
done
exec "REAL_SED_PATH_TOKEN" "$@"
"""

    @classmethod
    def _write_hostile_bsd_sed_shim(cls, directory):
        """Writes an executable ``sed`` into ``directory`` that hard-fails
        on any bare ``-i`` token (mimicking real BSD/macOS sed's mandatory
        backup-suffix argument for ``-i``, which a bare ``-i`` never
        supplies) and otherwise delegates to the real system sed. Placing
        ``directory`` first on ``PATH`` makes every ``sed`` invocation in
        a subprocess -- including every one inside a Make recipe's shell
        -- go through this shim instead.
        """
        real_sed = shutil.which("sed")
        assert real_sed, "a real system sed is required to build this shim"
        script = cls._HOSTILE_SED_SHIM_TEMPLATE.replace(
            "HOSTILE_SED_FAILURE_MARKER_TOKEN", cls.HOSTILE_SED_FAILURE_MARKER
        ).replace("REAL_SED_PATH_TOKEN", real_sed)
        shim = Path(directory) / "sed"
        shim.write_text(script, encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return shim

    def setUp(self):
        ModernLocalizationHeaderBootstrapTests._clean_localization_output()
        self.addCleanup(
            ModernLocalizationHeaderBootstrapTests._clean_localization_output
        )

    # Matches an actual *recipe* line (tab-indented shell command,
    # optionally after Make's leading "@") invoking bare `sed ... -i`,
    # never prose in a comment discussing it (this file's own modern.mk
    # comment right above the fixed recipe deliberately quotes the old
    # broken invocation as documentation, so a plain substring check
    # would false-positive on that comment).
    _BARE_SED_DASH_I_RECIPE_RE = re.compile(
        r"^\t@?sed\b[^\n]*\s-i(\s|$)", re.MULTILINE
    )

    def test_source_never_uses_bare_sed_dash_i_for_header_filter(self):
        # Cheap, fast, supplementary guard only -- see class docstring for
        # why this can never be the sole regression test for this fix.
        # Checked against actual recipe lines, not prose, so this fixed
        # file's own explanatory comment (which quotes the old broken
        # invocation on purpose) can never make this assertion vacuous.
        match = self._BARE_SED_DASH_I_RECIPE_RE.search(self.MODERN_MK)
        self.assertIsNone(
            match,
            "a Make recipe line invokes bare `sed ... -i` "
            f"({match.group(0) if match else ''!r}) -- this breaks "
            "macOS/Homebrew's BSD sed, which requires an explicit "
            "backup-suffix argument for -i",
        )
        self.assertIn(
            '> "$@.tmp2"', self.MODERN_MK,
            "the .headers.d bare-token filter must redirect to a second "
            "per-target temp file and atomically rename it over the real "
            "target, rather than editing in place with sed -i",
        )

    def _run_hostile_sed_isolated_headers_d_build(self, config):
        if not _toolchain_available():
            self.skipTest("modern toolchain not available")
        with tempfile.TemporaryDirectory() as tmp:
            shim_dir = Path(tmp) / "hostile-sed-bin"
            shim_dir.mkdir()
            self._write_hostile_bsd_sed_shim(shim_dir)

            iso_root = Path(tmp) / "iso-build"
            env = dict(os.environ)
            env["PATH"] = "{}{}{}".format(
                shim_dir, os.pathsep, env.get("PATH", "")
            )

            # The top-level Makefile unconditionally exports
            # `PATH := $(TOOLCHAIN)/bin:$(PATH)` (legacy devkitARM lookup,
            # independent of the modern arm-none-eabi- toolchain used by
            # this recipe). When TOOLCHAIN/DEVKITARM is unset (as in a
            # bare modern-only environment, and in CI), `$(TOOLCHAIN)/bin`
            # collapses to the literal path "/bin", which on most Linux
            # hosts really does contain a real `sed` -- accidentally
            # shadowing this hostile shim ahead of it on PATH and making
            # this test a false pass. Pointing TOOLCHAIN at an empty,
            # sed-free throwaway directory keeps that legacy PATH prefix
            # harmless (nothing here builds a legacy, non-modern target)
            # while guaranteeing PATH resolution actually falls through
            # to this shim's directory, next in line.
            toolchain_dir = Path(tmp) / "empty-legacy-toolchain"
            toolchain_dir.mkdir()

            headers_d_targets = [
                str(iso_root / config / "aapcs" / Path(source).with_suffix(".headers.d"))
                for source in CONSUMER_SOURCES
            ]
            result = self._make(
                *headers_d_targets,
                f"MODERN_CONFIG={config}",
                f"MODERN_BUILD_ROOT={iso_root}",
                f"TOOLCHAIN={toolchain_dir}",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout[-3000:])
            self.assertNotIn(
                self.HOSTILE_SED_FAILURE_MARKER, result.stdout,
                "the .headers.d recipe invoked `sed -i` -- this breaks "
                "real BSD/macOS sed the same way this fake shim just "
                "did",
            )
            self._assert_no_missing_rule(result.stdout)

            for target in headers_d_targets:
                target_path = Path(target)
                self.assertTrue(
                    target_path.is_file(),
                    f"{target_path} was not produced under the hostile "
                    f"fake-sed PATH",
                )
                text = target_path.read_text(encoding="utf-8")
                self.assertNotRegex(
                    text, r"(?:^|[\s\\])expansion_msg_ids\.h(?:$|\s)",
                    f"{target_path} still lists the bare, unresolvable "
                    f"expansion_msg_ids.h token even under a hostile "
                    f"fake sed -- the filter must still take effect "
                    f"without relying on `sed -i`",
                )

    _make = ModernLocalizationHeaderBootstrapTests._make
    _assert_no_missing_rule = (
        ModernLocalizationHeaderBootstrapTests._assert_no_missing_rule
    )

    def test_debug_cold_headers_d_filter_survives_hostile_bsd_like_sed(self):
        self._run_hostile_sed_isolated_headers_d_build("debug")

    def test_release_cold_headers_d_filter_survives_hostile_bsd_like_sed(self):
        self._run_hostile_sed_isolated_headers_d_build("release")


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
