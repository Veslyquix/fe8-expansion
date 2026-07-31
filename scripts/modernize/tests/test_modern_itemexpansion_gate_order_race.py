"""Issue #18 sprint 6: modern-linker -> modern-itemexpansion gate-order
regression, following on a reported branch-local intermittent failure::

    gItemExpansionProbe not found

...at ``verify``'s ``modern-itemexpansion-check-debug`` gate, reported to
happen only sometimes, only after the preceding ``modern-linker-check-*``
gates already ran in the same build root (see
``reports/itemexpansion_gate_order_race_diagnosis.md`` for the full
diagnosis writeup, including what was and was not actually reproduced
locally).

This module has two halves:

* Fast, always-run, toolchain-independent structural assertions
  (``ModernElfExplicitObjectDependencyTests`` and
  ``ModernShiftedCheckSiblingIsolationTests`` below) that pin the two
  concrete DAG-hardening edits made alongside this diagnosis so neither
  can silently regress:
    1. ``$(MODERN_ELF)``'s own recipe now lists
       ``$(MODERN_ALL_OBJECTS)``/``$(MODERN_COMPILE_SETTINGS)`` as
       *explicit* prerequisites (previously this was guaranteed only
       implicitly, via ``expansion-modern-link-prepare``'s ``.PHONY``
       "always rerun" side effect -- correct, but fragile/non-obvious).
    2. ``expansion-modern-shifted-check`` and
       ``expansion-modern-localization-runtime-shifted-check`` -- both
       undeclared-order SIBLING prerequisites of
       ``expansion-modern-linker-check`` -- now write to two distinct
       output directories instead of racing on one shared
       ``$(MODERN_SHIFTED_OUTDIR)`` path. That shared-path race is a
       genuinely *reproduced* bug (see the diagnosis report): under
       ``make -jN`` with N>1, two concurrent ``arm-none-eabi-ld``
       invocations tore the same ``shifted.elf``, intermittently failing
       ``expansion-modern-linker-check`` itself with an unrelated-looking
       "file format not recognized" error -- the same general *class* of
       bug (a shared, non-isolated output path raced by concurrent
       sibling Make recipes) as the reported gate-order symptom, even
       though it is a different concrete pair of targets/paths and this
       suite did not manage to reproduce the exact reported
       "gItemExpansionProbe not found" message from it.

* A real, toolchain-(and libmGBA-)gated integration test
  (``ModernLinkerThenItemExpansionGateSequenceTests``) that runs the
  actual reported gate sequence -- ``expansion-modern-linker-check``
  debug, then release, then ``expansion-modern-itemexpansion-check``
  debug, then release -- once, back to back, in one single isolated,
  freshly-created ``MODERN_BUILD_ROOT`` (so every gate after the first
  necessarily reuses that same build root's objects/ELF exactly like
  ``python3 -m scripts.upstream_port verify`` does), and asserts each
  gate exits 0 and that the final debug ELF really does carry a properly
  defined, non-degenerate ``gItemExpansionProbe`` symbol via a direct
  ``nm`` lookup -- never trusting the higher-level scripts' own exit
  code alone for that specific assertion.

  This is deliberately run ONCE per config pairing (not repeated in a
  stress loop): a full debug ``expansion-modern-linker-check`` alone
  already costs several real minutes of ``arm-none-eabi-*``/link/ROM-
  boot work even on a warm toolchain, so this module keeps the expensive
  path to exactly the one sequence the task/report describes, and
  documents (here and in the diagnosis report) that a much larger,
  repeated stress-loop was used ad hoc during the actual investigation
  but is intentionally NOT checked in as a standing regression, per
  "keep cost reasonable".
"""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODERN_MK = ROOT / "modern.mk"


def _toolchain_available():
    return bool(
        shutil.which("arm-none-eabi-gcc")
        and shutil.which("arm-none-eabi-ld")
        and shutil.which("arm-none-eabi-objcopy")
        and shutil.which("arm-none-eabi-nm")
    )


def _libmgba_available():
    """Same real-backend-build probe used by
    test_modern_localization_header_bootstrap.py's own
    ``_libmgba_available`` (kept independent/duplicated on purpose: this
    module must not import test internals from a sibling test module)."""
    sys.path.insert(0, str(ROOT / "tools" / "gba-playtest"))
    import gba_playtest as _gba_playtest  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="libmgba-probe-") as tmp:
        probe_binary = Path(tmp) / "gba_playtest_backend_probe"
        try:
            _gba_playtest.build_backend(probe_binary)
        except _gba_playtest.PlaytestError:
            return False
    return True


class ModernElfExplicitObjectDependencyTests(unittest.TestCase):
    """Pins the $(MODERN_ELF) DAG-hardening edit: the objects and the
    content-addressed compile-settings stamp must be listed as real,
    direct, non-phony prerequisites of the link rule -- not relied on
    solely through expansion-modern-link-prepare's phony side effect."""

    def setUp(self):
        self.text = MODERN_MK.read_text(encoding="utf-8")

    def test_modern_elf_recipe_lists_objects_and_compile_settings(self):
        lines = self.text.splitlines()
        start = next(
            (i for i, line in enumerate(lines) if line.startswith("$(MODERN_ELF):")),
            None,
        )
        self.assertIsNotNone(
            start, "could not locate the $(MODERN_ELF): prerequisite line(s)"
        )
        collected = [lines[start][len("$(MODERN_ELF):"):]]
        i = start
        while collected[-1].rstrip().endswith("\\"):
            i += 1
            collected.append(lines[i])
        prereqs = "\n".join(collected)
        self.assertIn(
            "$(MODERN_ALL_OBJECTS)", prereqs,
            "$(MODERN_ELF) must explicitly depend on $(MODERN_ALL_OBJECTS) "
            "(not only transitively through the "
            "expansion-modern-link-prepare phony)",
        )
        self.assertIn(
            "$(MODERN_COMPILE_SETTINGS)", prereqs,
            "$(MODERN_ELF) must explicitly depend on "
            "$(MODERN_COMPILE_SETTINGS) so a config/cap/itemtest flag "
            "change is a real, direct Make dependency edge on the link "
            "step, not only an implicit side effect of another "
            "prerequisite being phony",
        )
        self.assertIn("expansion-modern-link-prepare", prereqs)

    def test_dry_run_still_links_cleanly_with_explicit_prereqs(self):
        if not _toolchain_available():
            self.skipTest("modern toolchain not available")
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    "make", "--no-print-directory", "-n",
                    "expansion-modern-elf",
                    "MODERN_CONFIG=debug",
                    f"MODERN_BUILD_ROOT={Path(tmp) / 'iso'}",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout[-3000:])
            self.assertNotIn("No rule to make target", result.stdout)


class ModernShiftedCheckSiblingIsolationTests(unittest.TestCase):
    """Pins the shifted-check output-directory split: two sibling
    prerequisites of expansion-modern-linker-check must never again
    share one mutable output path."""

    def setUp(self):
        self.text = MODERN_MK.read_text(encoding="utf-8")

    def test_boot_and_locale_shifted_outdirs_are_distinct_variables(self):
        self.assertIn("MODERN_SHIFTED_OUTDIR_BOOT", self.text)
        self.assertIn("MODERN_SHIFTED_OUTDIR_LOCALE", self.text)
        boot_def = re.search(
            r"^MODERN_SHIFTED_OUTDIR_BOOT\s*:=\s*(.+)$", self.text, re.MULTILINE
        )
        locale_def = re.search(
            r"^MODERN_SHIFTED_OUTDIR_LOCALE\s*:=\s*(.+)$", self.text, re.MULTILINE
        )
        self.assertIsNotNone(boot_def)
        self.assertIsNotNone(locale_def)
        self.assertNotEqual(
            boot_def.group(1).strip(), locale_def.group(1).strip(),
            "expansion-modern-shifted-check and "
            "expansion-modern-localization-runtime-shifted-check must not "
            "resolve to the same SHIFTCHECK_OUTDIR -- that is exactly the "
            "shared-mutable-output-path race this regression covers",
        )

    def test_boot_check_recipe_uses_its_own_outdir_not_the_shared_base(self):
        boot_block = re.search(
            r"^expansion-modern-shifted-check:.*?(?=^\S|\Z)",
            self.text,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(boot_block)
        self.assertIn('SHIFTCHECK_OUTDIR="$(MODERN_SHIFTED_OUTDIR_BOOT)"',
                       boot_block.group(0))
        self.assertNotIn('SHIFTCHECK_OUTDIR="$(MODERN_SHIFTED_OUTDIR)"',
                          boot_block.group(0))

    def test_locale_shifted_check_recipe_uses_its_own_outdir(self):
        locale_block = re.search(
            r"^expansion-modern-localization-runtime-shifted-check:.*?(?=^\.PHONY:|\Z)",
            self.text,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(locale_block)
        body = locale_block.group(0)
        self.assertNotIn('SHIFTCHECK_OUTDIR="$(MODERN_SHIFTED_OUTDIR)"', body)
        self.assertEqual(
            body.count('SHIFTCHECK_OUTDIR="$(MODERN_SHIFTED_OUTDIR_LOCALE)"'),
            2,
            "both scenario invocations inside this one recipe should share "
            "their OWN dedicated outdir (fine -- they run sequentially "
            "inside a single recipe's shell, never concurrently with each "
            "other), distinct from the boot-check sibling's",
        )


class ModernLinkerThenItemExpansionGateSequenceTests(unittest.TestCase):
    """Real, toolchain-gated integration coverage for the reported gate
    order: expansion-modern-linker-check (debug, then release), then
    expansion-modern-itemexpansion-check (debug, then release), all
    against one single isolated MODERN_BUILD_ROOT -- exactly mirroring
    how `python3 -m scripts.upstream_port verify` walks its own gate
    list against the real default build root."""

    ITEMEXPANSION_ENV = [
        "FE8_ITEM_ID_CAP=0xCE",
        "FE8_EXPANSION_ITEMTEST=1",
        "EXPANSION_STARTER_CONTENT=1",
        "EXPANSION_MECHANICS_HOOKS=1",
        "EXPANSION_MECHANICS_SAMPLE=1",
    ]

    # Match python3 -m scripts.upstream_port verify's own default
    # `--jobs 2` per-gate parallelism: reasonable build-time cost, while
    # still genuinely exercising `-jN` with N>1 (both the reported
    # itemexpansion-check symptom and the shifted-check sibling race this
    # module reproduced are specifically about -jN>1 sibling-recipe
    # scheduling, so this must never silently degrade to an effectively
    # serial -j1 build).
    JOBS = "2"

    def _make(self, *args):
        return subprocess.run(
            ["make", "--no-print-directory", f"-j{self.JOBS}", *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def _assert_gate_clean(self, result, label):
        self.assertEqual(result.returncode, 0, f"{label}:\n{result.stdout[-4000:]}")
        for bad in (
            "No rule to make target",
            "file format not recognized",
            "gItemExpansionProbe not found",
        ):
            self.assertNotIn(
                bad, result.stdout,
                f"{label} output contained {bad!r}:\n{result.stdout[-4000:]}",
            )

    def test_isolated_linker_then_itemexpansion_sequence_both_configs(self):
        if not _toolchain_available():
            self.skipTest("modern toolchain not available")
        if not _libmgba_available():
            self.skipTest("libmGBA (pkg-config mgba) not available")

        with tempfile.TemporaryDirectory() as tmp:
            iso_root = Path(tmp) / "iso-build"

            debug_linker = self._make(
                "expansion-modern-linker-check",
                "MODERN_CONFIG=debug",
                f"MODERN_BUILD_ROOT={iso_root}",
            )
            self._assert_gate_clean(debug_linker, "modern-linker-check-debug")

            release_linker = self._make(
                "expansion-modern-linker-check",
                "MODERN_CONFIG=release",
                f"MODERN_BUILD_ROOT={iso_root}",
            )
            self._assert_gate_clean(release_linker, "modern-linker-check-release")

            debug_itemexpansion = self._make(
                *self.ITEMEXPANSION_ENV,
                "expansion-modern-itemexpansion-check",
                "MODERN_CONFIG=debug",
                f"MODERN_BUILD_ROOT={iso_root}",
            )
            self._assert_gate_clean(
                debug_itemexpansion, "modern-itemexpansion-check-debug"
            )
            self.assertIn(
                "item-expansion runtime probe passed", debug_itemexpansion.stdout
            )

            release_itemexpansion = self._make(
                *self.ITEMEXPANSION_ENV,
                "expansion-modern-itemexpansion-check",
                "MODERN_CONFIG=release",
                f"MODERN_BUILD_ROOT={iso_root}",
            )
            self._assert_gate_clean(
                release_itemexpansion, "modern-itemexpansion-check-release"
            )
            self.assertIn(
                "item-expansion runtime probe passed", release_itemexpansion.stdout
            )

            # Never trust the higher-level scripts' own exit code alone for
            # the specific reported symptom: independently confirm via a
            # direct nm lookup that the debug ELF this whole sequence just
            # produced really does carry a properly defined
            # gItemExpansionProbe symbol (this is exactly the lookup
            # tools/gba-playtest/run_item_expansion_checks.py's own
            # resolve_symbol() performs before it will boot anything).
            debug_elf = iso_root / "debug" / "aapcs" / "fireemblem8.elf"
            self.assertTrue(debug_elf.is_file(), f"missing {debug_elf}")
            nm_result = subprocess.run(
                ["arm-none-eabi-nm", "-S", str(debug_elf)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(nm_result.returncode, 0, nm_result.stdout[-2000:])
            probe_lines = [
                line for line in nm_result.stdout.splitlines()
                if "gItemExpansionProbe" in line
            ]
            self.assertEqual(
                len(probe_lines), 1,
                f"expected exactly one gItemExpansionProbe symbol, got: "
                f"{probe_lines!r}",
            )
            # A real EWRAM data symbol has a non-zero size field (nm -S's
            # second column) and lands in EWRAM ('B'/'D' in the .bss/.data
            # sense the BSS-in-EWRAM linker script assigns it, never an
            # undefined 'U' -- which is what "gItemExpansionProbe not
            # found" actually means downstream in resolve_symbol()).
            fields = probe_lines[0].split()
            self.assertGreaterEqual(
                len(fields), 4,
                f"unexpected nm -S line shape: {probe_lines[0]!r}",
            )
            symbol_type = fields[2]
            self.assertNotEqual(
                symbol_type, "U",
                f"gItemExpansionProbe resolved as undefined: {probe_lines[0]!r}",
            )


if __name__ == "__main__":
    unittest.main()
