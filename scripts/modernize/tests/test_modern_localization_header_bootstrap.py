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

import json
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



class ModernLocalizationPrefsCheckColdIsolatedRootTests(unittest.TestCase):
    """Issue #18 sprint 6 verifier-blocker regression.

    ``expansion-modern-localization-runtime-prefs-check``'s three
    no-wipe scenarios (corrupt/unknown-locale/disabled-locale
    ``ExpansionUserPrefs``) used to fail to reproduce their own committed
    fingerprints under *any* freshly (re)built ``MODERN_BUILD_ROOT`` --
    the default/canonical one included -- because
    ``tools/gba-playtest/tests/locale_prefs_fixture.py``'s host-crafted
    outer ``ExpansionSaveMeta.buildCommitShort`` was stamped from this
    host's *live* ``git rev-parse HEAD`` (via
    ``save_format_tool.py``'s ``build_current_expansion_save_meta()``),
    which silently changes on every commit and invalidates the
    committed fingerprint's checksum-derived probe bytes the very next
    commit, independent of which build root ran it. Fixed by freezing
    that diagnostic-only field to sram_fixture.py's own
    ``DETERMINISTIC_BUILD_COMMIT_SHORT`` sentinel (see
    ``locale_prefs_fixture.py``'s own docstring and
    ``_freeze_diagnostic_build_commit()``), and by making every
    ``*.sav`` fixture target in modern.mk depend on its real generator
    scripts and ``config.mk`` so a stale cached ``.sav`` from a previous
    revision is never silently reused.

    These tests run the *real* ``expansion-modern-localization-runtime-
    prefs-check`` target end to end (real toolchain + real libmGBA),
    twice, against two distinct, throwaway ``MODERN_BUILD_ROOT``
    directories that share nothing with each other or with any
    repository-tracked ``build/`` cache -- proving the fix holds for a
    genuinely isolated build root, not merely the canonical default one.
    """

    def _run_cold_prefs_check(self, config, build_root):
        result = subprocess.run(
            [
                "make", "--no-print-directory",
                "expansion-modern-localization-runtime-prefs-check",
                f"MODERN_CONFIG={config}",
                "MODERN_ABI=aapcs",
                f"MODERN_BUILD_ROOT={build_root}",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-6000:])
        self.assertNotIn(
            "No rule to make target", result.stdout,
            "cold expansion-modern-localization-runtime-prefs-check must "
            "never hit an unresolvable generated-header prerequisite",
        )
        self.assertIn(
            "localization-runtime prefs-check passed", result.stdout,
        )
        return result

    def test_debug_two_distinct_isolated_roots_both_pass_with_deterministic_fixtures(self):
        if not _toolchain_available():
            self.skipTest("modern toolchain not available")
        if not _libmgba_available():
            self.skipTest("libmGBA (pkg-config mgba) not available")

        fixture_names = ("corrupt.sav", "unknown.sav", "disabled_on_default.sav")

        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            root_a = Path(tmp_a) / "iso-build-a"
            root_b = Path(tmp_b) / "iso-build-b"
            self.assertNotEqual(
                root_a, root_b,
                "the two isolated build roots must be genuinely distinct",
            )

            self._run_cold_prefs_check("debug", root_a)
            self._run_cold_prefs_check("debug", root_b)

            fixtures_a = root_a / "debug" / "aapcs" / "locale-fixtures"
            fixtures_b = root_b / "debug" / "aapcs" / "locale-fixtures"
            for name in fixture_names:
                path_a = fixtures_a / name
                path_b = fixtures_b / name
                self.assertTrue(path_a.is_file(), f"{path_a} was not generated")
                self.assertTrue(path_b.is_file(), f"{path_b} was not generated")
                self.assertEqual(
                    path_a.read_bytes(), path_b.read_bytes(),
                    f"{name} must be byte-identical across independent "
                    f"isolated MODERN_BUILD_ROOT invocations -- any "
                    f"difference means fixture generation still depends "
                    f"on something other than this repository's own "
                    f"config.mk/generator scripts (e.g. live git history "
                    f"or a canonical-build-only cache)",
                )


class ModernLocalizationPrefsFixtureStaticDeterminismTests(unittest.TestCase):
    """Static, fast, supplementary guards (never the sole coverage --
    see ``ModernLocalizationPrefsCheckColdIsolatedRootTests`` above for
    the real end-to-end regression) against reintroducing either half of
    this sprint's verifier-blocker fix:

    1. ``locale_prefs_fixture.py`` must never go back to stamping
       ``ExpansionSaveMeta.buildCommitShort`` straight from
       ``save_format_tool.py``'s live-git-derived
       ``build_current_expansion_save_meta()`` result without freezing
       it first.
    2. modern.mk's ``*.sav`` fixture targets must never hardcode the
       canonical default build root's literal on-disk path
       (``build/expansion-modern/...``) in place of the
       ``MODERN_BUILD_ROOT``-derived ``$(MODERN_LOCALE_FIXTURE_DIR)``
       variable -- doing so would silently make every fixture always
       land under (and be read back from) the one repository-tracked
       canonical build tree regardless of a caller's own
       ``MODERN_BUILD_ROOT`` override, defeating the whole point of the
       isolated-root regression above.
    """

    REPO_ROOT = Path(__file__).resolve().parents[3]
    LOCALE_PREFS_FIXTURE_PY = (
        REPO_ROOT / "tools" / "gba-playtest" / "tests" / "locale_prefs_fixture.py"
    ).read_text(encoding="utf-8")
    MODERN_MK = (REPO_ROOT / "modern.mk").read_text(encoding="utf-8")

    def test_prefs_fixture_freezes_diagnostic_build_commit(self):
        self.assertIn(
            "_freeze_diagnostic_build_commit", self.LOCALE_PREFS_FIXTURE_PY,
            "locale_prefs_fixture.py must freeze ExpansionSaveMeta."
            "buildCommitShort to a fixed sentinel instead of stamping "
            "this host's live git commit into a fixture whose checksum "
            "gets baked into a committed fingerprint",
        )
        self.assertIn(
            "sram_fixture.DETERMINISTIC_BUILD_COMMIT_SHORT",
            self.LOCALE_PREFS_FIXTURE_PY,
            "the frozen sentinel must be sram_fixture.py's own "
            "already-reviewed DETERMINISTIC_BUILD_COMMIT_SHORT constant, "
            "never a new hand-written/duplicated placeholder value",
        )

    # Matches a modern.mk fixture-target *rule* line building one of the
    # three no-wipe fixtures with a hardcoded "build/expansion-modern"
    # literal instead of the MODERN_BUILD_ROOT-derived
    # $(MODERN_LOCALE_FIXTURE_DIR) variable. Deliberately anchored on the
    # actual rule header (target followed by ':') so it can never
    # false-positive on this file's own prose/comments mentioning the
    # canonical default path elsewhere.
    _HARDCODED_CANONICAL_FIXTURE_RULE_RE = re.compile(
        r"^build/expansion-modern/\S*\.sav\s*:", re.MULTILINE
    )

    def test_fixture_rules_never_hardcode_canonical_build_root(self):
        match = self._HARDCODED_CANONICAL_FIXTURE_RULE_RE.search(self.MODERN_MK)
        self.assertIsNone(
            match,
            "a modern.mk fixture rule hardcodes the canonical default "
            f"build root ({match.group(0) if match else ''!r}) instead of "
            "the MODERN_BUILD_ROOT-derived $(MODERN_LOCALE_FIXTURE_DIR) "
            "-- this would make the fixture always resolve to the one "
            "repository-tracked build tree regardless of a caller's own "
            "MODERN_BUILD_ROOT override",
        )
        for name in ("blank.sav", "unset.sav", "corrupt.sav", "unknown.sav",
                     "disabled_on_default.sav"):
            self.assertIn(
                f"$(MODERN_LOCALE_FIXTURE_DIR)/{name}", self.MODERN_MK,
                f"{name}'s fixture rule must be keyed off the "
                f"MODERN_BUILD_ROOT-derived $(MODERN_LOCALE_FIXTURE_DIR)",
            )



SCENARIOS_DIR = ROOT / "tools" / "gba-playtest" / "scenarios"
FINGERPRINTS_DIR = ROOT / "tools" / "gba-playtest" / "fingerprints"

# Issue #18 sprint 7 real repair matrix: 4 ExpansionUserPrefs sub-states
# that require a re-prompt (never VALID/MIGRATED) x 2 MODERN_CONFIG
# values = 8 mandatory real libmGBA scenarios -- see docs/localization.md
# and modern.mk's expansion-modern-localization-runtime-multi-check.
REPAIR_STATES = ("unset", "corrupt", "unknown", "disabled")
REPAIR_CONFIGS = ("debug", "release")

# Mirrors include/expansion_language_menu.h's
# enum ExpansionLanguageMenuPromptReason / src/bmsave-lib.c's
# enum ExpansionUserPrefsState ordinal values -- never re-derived, always
# cross-checked against the real, unmodified header by
# tools/gba-playtest/tests/test_locale_probe_schema.py's own
# offsetof()/sizeof() compiler-driven layout (this module only needs the
# *values*, not the byte layout, which that other suite already locks
# in).
REPAIR_PROMPT_REASON = {"unset": 0x01, "corrupt": 0x02, "unknown": 0x03, "disabled": 0x04}
REPAIR_PREFS_STATE = {"unset": 0x00, "corrupt": 0x01, "unknown": 0x02, "disabled": 0x03}
REPAIR_PREFS_STATE_VALID = 0x05

REPAIR_FIXTURE_FOR_STATE = {
    "unset": "unset.sav",
    "corrupt": "corrupt.sav",
    "unknown": "unknown.sav",
    "disabled": "disabled_on_multi.sav",
}

# gExpansionLanguageMenuProbe's own EWRAM base address per config -- see
# tools/gba-playtest/scenarios/locale-blank-sram-selector-multi-modern-
# {debug,release}.json's own probe addresses (this module never invents
# these; they are the same literal bases every other locale-*.json
# scenario in this repository already uses).
REPAIR_EWRAM_BASE = {"debug": 0x02031A94, "release": 0x02031588}

# struct ExpansionLanguageMenuProbe field byte offsets -- see include/
# expansion_language_menu.h's field declaration order, independently
# compiler-verified against every locale-*.json scenario (including this
# sprint's) by test_locale_probe_schema.py.
REPAIR_FIELD_OFFSET = {
    "active": 0, "settingsActive": 1, "promptShown": 2, "autoSelected": 3,
    "promptReason": 4, "prefsState": 5, "selectedLocale": 6, "currentLocale": 7,
    "enabledLocaleCount": 8, "cacheGeneration": 10, "startupRunCount": 12,
    "settingsOpenCount": 14, "settingsChangeCount": 16, "needsPreferenceRepair": 18,
}

REQUIRED_REPAIR_CHECKPOINT_NAMES = (
    "pre-runtimeinit-sram-baseline",
    "pre-repair-selector-shown",
    "selector-after-navigate-down",
    "selector-after-navigate-back-to-en",
    "post-repair-committed",
    "post-reset-ewram-fresh",
    "post-reset-selector-skipped-en-restored",
)


class ModernLocalizationRepairMatrixTests(unittest.TestCase):
    """Issue #18 sprint 7: host tests enumerating the exact 4 (prefs
    sub-state) x 2 (MODERN_CONFIG) = 8 real repair-matrix scenario/
    fingerprint pairs (``locale-repair-<state>-multi-modern-
    <config>.json``), their required checkpoint/probe/input semantics,
    their fixture mapping, and their modern.mk target wiring.

    These are static/structural checks (no libmGBA/toolchain
    dependency -- always run) that fail loudly if:

    * any of the 8 scenario or fingerprint files is missing (including a
      release pair -- these are never debug-only/skipped, unlike the
      single-locale AUTO_SELECT no-wipe checks);
    * a scenario ever encodes ``autoSelected`` as anything but ``0x00``
      (i.e. never collapses to AUTO_SELECT -- that would silently
      readopt the single-locale gap this sprint closes) or fails to show
      the real blocking selector (``active``/``promptShown``/
      ``needsPreferenceRepair`` all 1) with the correct per-state
      ``promptReason``/``prefsState`` pair;
    * the required checkpoint sequence (prompt shown -> real navigate ->
      commit -> soft-reset -> post-reset settle) is not present, or the
      literal ``A``+``B``+``SELECT``+``START`` soft-reset combo is
      missing from the input timeline;
    * the persisted-record/no-wipe/VALID-after-reboot proof bytes are
      not asserted;
    * modern.mk's ``expansion-modern-localization-runtime-multi-check``
      does not wire every one of the 8 pairs, or wires them inside the
      ``ifeq ($(MODERN_CONFIG),debug)`` guard that gates the debug-only
      scenarios (which would silently skip the release half of the
      matrix).
    """

    MODERN_MK = (ROOT / "modern.mk").read_text(encoding="utf-8")

    @staticmethod
    def _scenario_path(state, config):
        return SCENARIOS_DIR / f"locale-repair-{state}-multi-modern-{config}.json"

    @staticmethod
    def _fingerprint_path(state, config):
        return FINGERPRINTS_DIR / f"locale-repair-{state}-multi-modern-{config}.json"

    def _load_scenario(self, state, config):
        path = self._scenario_path(state, config)
        self.assertTrue(path.is_file(), f"missing scenario file: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _checkpoint_by_name(self, data, name):
        for checkpoint in data["checkpoints"]:
            if checkpoint["name"] == name:
                return checkpoint
        self.fail(f"{data['name']}: missing required checkpoint {name!r}")

    def _probe_value(self, checkpoint, base, field):
        address = "0x%08x" % (base + REPAIR_FIELD_OFFSET[field])
        for probe in checkpoint["probes"]:
            if probe["address"] == address:
                return probe.get("expected")
        self.fail(
            f"{checkpoint['name']}: missing probe for field {field!r} "
            f"(address {address})"
        )

    def test_all_8_scenario_and_fingerprint_files_exist(self):
        missing = []
        for state in REPAIR_STATES:
            for config in REPAIR_CONFIGS:
                if not self._scenario_path(state, config).is_file():
                    missing.append(f"scenario locale-repair-{state}-multi-modern-{config}.json")
                if not self._fingerprint_path(state, config).is_file():
                    missing.append(f"fingerprint locale-repair-{state}-multi-modern-{config}.json")
        self.assertEqual(
            missing, [],
            f"the real repair matrix must cover all 4 states x 2 configs "
            f"(release pairs are mandatory, never skipped); missing: {missing}",
        )

    def test_every_scenario_has_the_required_checkpoint_sequence(self):
        for state in REPAIR_STATES:
            for config in REPAIR_CONFIGS:
                data = self._load_scenario(state, config)
                names = {c["name"] for c in data["checkpoints"]}
                for required in REQUIRED_REPAIR_CHECKPOINT_NAMES:
                    self.assertIn(
                        required, names,
                        f"locale-repair-{state}-multi-modern-{config}.json is "
                        f"missing required checkpoint {required!r}",
                    )

    def test_every_scenario_sends_the_literal_soft_reset_combo(self):
        for state in REPAIR_STATES:
            for config in REPAIR_CONFIGS:
                data = self._load_scenario(state, config)
                combos = [set(f["keys"]) for f in data["frames"]]
                self.assertIn(
                    {"A", "B", "SELECT", "START"}, combos,
                    f"locale-repair-{state}-multi-modern-{config}.json must "
                    "send the literal A+B+SELECT+START soft-reset combo, "
                    "never a host-side reset call",
                )

    def test_prompt_checkpoint_never_uses_auto_select_and_matches_its_own_state(self):
        for state in REPAIR_STATES:
            for config in REPAIR_CONFIGS:
                data = self._load_scenario(state, config)
                base = REPAIR_EWRAM_BASE[config]
                cp = self._checkpoint_by_name(data, "pre-repair-selector-shown")
                self.assertEqual(self._probe_value(cp, base, "active"), "0x01")
                self.assertEqual(
                    self._probe_value(cp, base, "autoSelected"), "0x00",
                    f"locale-repair-{state}-multi-modern-{config}.json's prompt "
                    "checkpoint must never show autoSelected=1 -- this build "
                    "enables 2 locales, so the real blocking selector (never "
                    "AUTO_SELECT) must be the one exercised here",
                )
                self.assertEqual(self._probe_value(cp, base, "needsPreferenceRepair"), "0x01")
                self.assertEqual(
                    self._probe_value(cp, base, "promptReason"),
                    "0x%02x" % REPAIR_PROMPT_REASON[state],
                )
                self.assertEqual(
                    self._probe_value(cp, base, "prefsState"),
                    "0x%02x" % REPAIR_PREFS_STATE[state],
                )

    def test_commit_checkpoint_proves_store_and_clears_repair_flag(self):
        for state in REPAIR_STATES:
            for config in REPAIR_CONFIGS:
                data = self._load_scenario(state, config)
                base = REPAIR_EWRAM_BASE[config]
                cp = self._checkpoint_by_name(data, "post-repair-committed")
                self.assertEqual(self._probe_value(cp, base, "active"), "0x00")
                self.assertEqual(self._probe_value(cp, base, "needsPreferenceRepair"), "0x00")
                self.assertEqual(self._probe_value(cp, base, "cacheGeneration"), "0x0001")
                self.assertTrue(
                    cp.get("sram_hash"),
                    f"locale-repair-{state}-multi-modern-{config}.json's commit "
                    "checkpoint must hash the whole SRAM image (minus the "
                    "documented exclusions) to prove no-wipe",
                )
                addresses = {p["address"]: p.get("expected") for p in cp["probes"]}
                self.assertEqual(addresses.get("0x0e0073d4"), "0xa5")
                self.assertEqual(addresses.get("0x0e0073d5"), "0x01")
                self.assertEqual(
                    addresses.get("0x0e0073d6"), "0x00",
                    "the persisted localeId byte must read English (0x00) -- "
                    "the explicit choose-default-en repair",
                )
                self.assertEqual(addresses.get("0x0e0073d7"), "0x01")

    def test_final_checkpoint_proves_valid_classification_and_no_reprompt(self):
        for state in REPAIR_STATES:
            for config in REPAIR_CONFIGS:
                data = self._load_scenario(state, config)
                base = REPAIR_EWRAM_BASE[config]
                cp = self._checkpoint_by_name(data, "post-reset-selector-skipped-en-restored")
                self.assertEqual(self._probe_value(cp, base, "active"), "0x00")
                self.assertEqual(
                    self._probe_value(cp, base, "promptShown"), "0x00",
                    f"locale-repair-{state}-multi-modern-{config}.json must "
                    "prove the selector/prompt is absent after reboot",
                )
                self.assertEqual(
                    self._probe_value(cp, base, "prefsState"),
                    "0x%02x" % REPAIR_PREFS_STATE_VALID,
                    "the second real boot's own Normalize() must classify the "
                    "repaired record VALID",
                )
                self.assertEqual(self._probe_value(cp, base, "currentLocale"), "0x00")

    def test_baseline_and_commit_sram_hash_exclude_only_documented_ranges(self):
        expected_ranges = [
            {"offset": 29220, "length": 36},
            {"offset": 29600, "length": 4},
            {"offset": 29652, "length": 12},
        ]
        for state in REPAIR_STATES:
            for config in REPAIR_CONFIGS:
                data = self._load_scenario(state, config)
                for name in ("pre-runtimeinit-sram-baseline", "post-repair-committed"):
                    cp = self._checkpoint_by_name(data, name)
                    self.assertEqual(
                        cp.get("sram_hash_exclude_ranges"), expected_ranges,
                        f"locale-repair-{state}-multi-modern-{config}.json's "
                        f"{name!r} checkpoint must exclude exactly the "
                        "SoundRoomSaveData/SramInit-pad/ExpansionUserPrefs "
                        "ranges -- never widen the blind spot",
                    )

    def test_fixture_mapping_matches_locale_prefs_fixture_states(self):
        # Cross-checked against the real fixture-state constants (never a
        # re-typed literal) -- see tools/gba-playtest/tests/
        # locale_prefs_fixture.py.
        sys.path.insert(0, str(ROOT / "tools" / "gba-playtest" / "tests"))
        import locale_prefs_fixture as lpf  # noqa: PLC0415

        state_const = {
            "unset": lpf.PREFS_STATE_UNSET,
            "corrupt": lpf.PREFS_STATE_CORRUPT,
            "unknown": lpf.PREFS_STATE_UNKNOWN_LOCALE,
            "disabled": lpf.PREFS_STATE_DISABLED_LOCALE,
        }
        self.assertEqual(set(state_const.values()), set(lpf.ALL_PREFS_FIXTURE_STATES))
        for state, fixture_name in REPAIR_FIXTURE_FOR_STATE.items():
            expected_line = f"$(MODERN_LOCALE_FIXTURE_DIR)/{fixture_name}"
            self.assertIn(
                expected_line, self.MODERN_MK,
                f"modern.mk must define a fixture rule for {fixture_name} "
                f"(state {state_const[state]!r})",
            )

    def test_disabled_multi_fixture_uses_a_supported_but_not_enabled_locale_id(self):
        # The multi-locale build enables en(0)+qps-ploc(7); the disabled-
        # locale fixture for it must use a different, real, in-range
        # ExpansionLocaleId (JA=1) that is genuinely not enabled by that
        # build -- never reusing the single-locale build's own id=7
        # (which IS enabled on the multi-locale build, so it would no
        # longer classify DISABLED_LOCALE there).
        match = re.search(
            r"\$\(MODERN_LOCALE_FIXTURE_DIR\)/disabled_on_multi\.sav:.*?"
            r"--disabled-locale-id\s+(\d+)",
            self.MODERN_MK, re.DOTALL,
        )
        self.assertIsNotNone(match, "disabled_on_multi.sav fixture rule not found in modern.mk")
        self.assertEqual(
            match.group(1), "1",
            "disabled_on_multi.sav must use --disabled-locale-id 1 (JA), "
            "distinct from disabled_on_default.sav's id 7 (qps-ploc, which "
            "IS enabled on the multi-locale build)",
        )

    def test_multi_check_target_wires_all_8_pairs_unconditionally(self):
        target_start = self.MODERN_MK.index(
            "expansion-modern-localization-runtime-multi-check:"
        )
        # Bound the search to this target's own recipe body (up to the
        # next top-level target definition) so a match elsewhere in the
        # file can never produce a false pass.
        next_target = re.search(
            r"\n\S[^\n:]*:", self.MODERN_MK[target_start + 1:]
        )
        target_end = (
            target_start + 1 + next_target.start() if next_target else len(self.MODERN_MK)
        )
        target_body = self.MODERN_MK[target_start:target_end]

        debug_guard_idx = target_body.find("ifeq ($(MODERN_CONFIG),debug)")
        self.assertNotEqual(
            debug_guard_idx, -1,
            "expansion-modern-localization-runtime-multi-check must still "
            "guard its debug-only scenarios (locale-selector-multi-switch-qps "
            "etc.) behind ifeq ($(MODERN_CONFIG),debug)",
        )

        for state in REPAIR_STATES:
            scenario_ref = f"locale-repair-{state}-multi-modern-$(MODERN_CONFIG).json"
            fixture_ref = f"$(MODERN_LOCALE_FIXTURE_DIR)/{REPAIR_FIXTURE_FOR_STATE[state]}"
            self.assertIn(
                scenario_ref, target_body,
                f"expansion-modern-localization-runtime-multi-check must "
                f"invoke {scenario_ref} for both configs (via $(MODERN_CONFIG))",
            )
            self.assertIn(
                fixture_ref, target_body,
                f"expansion-modern-localization-runtime-multi-check must "
                f"feed {state} its own fixture ({fixture_ref})",
            )
            scenario_idx = target_body.index(scenario_ref)
            self.assertLess(
                scenario_idx, debug_guard_idx,
                f"{scenario_ref} must be wired OUTSIDE the "
                "ifeq ($(MODERN_CONFIG),debug) guard -- the repair matrix is "
                "mandatory for every config, never debug-only/skipped",
            )


if __name__ == "__main__":
    unittest.main()
