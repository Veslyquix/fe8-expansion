"""
Issue #6 host tests -- public battle-stat mechanics hook registry.

Where possible these compile and *execute* the real, unmodified project
sources (include/expansion_mechanics.h, src/expansion_mechanics.c, and the
src/bmbattle.c seam) with a native host compiler rather than pattern-matching
their logic, so a regression in the actual registry/sample/seam code is caught
here. The small driver sources live in tools/gba-playtest/tests/c/ and are
test-only (never referenced by modern.mk/Makefile).
"""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INCLUDE_DIRS = [REPO_ROOT / "include", REPO_ROOT / "include" / "generated"]
C_FIXTURES_DIR = Path(__file__).resolve().parent / "c"

MECHANICS_SRC = REPO_ROOT / "src" / "expansion_mechanics.c"
MECHANICS_HEADER = REPO_ROOT / "include" / "expansion_mechanics.h"
# The registry's single built-in install point also installs the issue #6
# bundled content example (a no-op stub unless FE8_EXPANSION_STARTER_CONTENT
# is 1), so the real content translation unit is linked here too -- the same
# "execute the real, unmodified sources" rule this module already follows.
CONTENT_SRC = REPO_ROOT / "src" / "expansion_starter_content.c"
BMBATTLE_SRC = REPO_ROOT / "src" / "bmbattle.c"

REGISTRY_DRIVER = C_FIXTURES_DIR / "expansion_mechanics_driver.c"
SAMPLE_DRIVER = C_FIXTURES_DIR / "expansion_mechanics_sample_driver.c"
DISABLED_DRIVER = C_FIXTURES_DIR / "expansion_mechanics_disabled_driver.c"

CC = shutil.which("gcc") or shutil.which("cc")
ARM_CC = shutil.which("arm-none-eabi-gcc")
NM = shutil.which("nm")


def _strip_c_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def _skip_if_no_host_compiler():
    if CC is None:
        raise unittest.SkipTest("no host C compiler (gcc/cc) available")


def _include_flags():
    flags = []
    for directory in INCLUDE_DIRS:
        flags += ["-I", str(directory)]
    return flags


def _compile(work_dir, src, obj_name, defines=(), extra=()):
    obj = Path(work_dir) / obj_name
    cmd = [CC, "-c", "-w"] + _include_flags()
    for define in defines:
        cmd += ["-D", define]
    cmd += list(extra) + [str(src), "-o", str(obj)]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr, obj


def _link(work_dir, objects, exe_name):
    exe = Path(work_dir) / exe_name
    cmd = [CC] + [str(o) for o in objects] + ["-o", str(exe)]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr, exe


def _run(exe):
    proc = subprocess.run([str(exe)], capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _defined_symbol_names(obj):
    if NM is None:
        raise unittest.SkipTest("no host 'nm' available")
    proc = subprocess.run([NM, str(obj)], capture_output=True, text=True)
    names = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] != "U":
            names.add(parts[2])
        elif len(parts) == 2 and parts[0] != "U":
            names.add(parts[1])
    return names


def _referenced_symbol_names(obj):
    """All symbol names referenced by obj (defined or undefined)."""
    if NM is None:
        raise unittest.SkipTest("no host 'nm' available")
    proc = subprocess.run([NM, str(obj)], capture_output=True, text=True)
    names = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        names.add(parts[-1])
    return names


class MechanicsRegistryHostTests(unittest.TestCase):
    """Compiles+executes the real registry (enabled) and its sample and
    disabled paths through the public API only."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def _build_and_run(self, tmp, defines, driver, exe):
        rc, out, mech_obj = _compile(tmp, MECHANICS_SRC, "mech.o", defines=defines)
        self.assertEqual(rc, 0, "compiling src/expansion_mechanics.c failed:\n" + out)
        rc, out, content_obj = _compile(tmp, CONTENT_SRC, "content.o", defines=defines)
        self.assertEqual(
            rc, 0, "compiling src/expansion_starter_content.c failed:\n" + out)
        rc, out, drv_obj = _compile(tmp, driver, "driver.o", defines=defines)
        self.assertEqual(rc, 0, "compiling %s failed:\n%s" % (driver.name, out))
        rc, out, exe_path = _link(tmp, [mech_obj, content_obj, drv_obj], exe)
        self.assertEqual(rc, 0, "linking failed:\n" + out)
        rc, out = _run(exe_path)
        return rc, out

    def test_registry_capacity_order_errors_and_reentrancy(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._build_and_run(
                tmp, ["FE8_EXPANSION_MECHANICS_HOOKS=1"], REGISTRY_DRIVER, "t_registry"
            )
        self.assertEqual(rc, 0, "registry host test failed:\n" + out)
        self.assertIn("MECHANICS_HOST_TEST: PASS", out)

    def test_sample_exact_effect_and_clamp(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._build_and_run(
                tmp,
                ["FE8_EXPANSION_MECHANICS_HOOKS=1", "FE8_EXPANSION_MECHANICS_SAMPLE=1"],
                SAMPLE_DRIVER,
                "t_sample",
            )
        self.assertEqual(rc, 0, "sample host test failed:\n" + out)
        self.assertIn("MECHANICS_SAMPLE_HOST_TEST: PASS", out)

    def test_disabled_path_is_inert_and_probe_stays_zero(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._build_and_run(tmp, [], DISABLED_DRIVER, "t_disabled")
        self.assertEqual(rc, 0, "disabled host test failed:\n" + out)
        self.assertIn("MECHANICS_DISABLED_HOST_TEST: PASS", out)


class MechanicsSeamWiringTests(unittest.TestCase):
    """Proves the src/bmbattle.c seam is present, correctly compile-gated, and
    byte-inert when disabled -- the disabled-vanilla-identity contract."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_seam_is_compile_gated_in_bmbattle(self):
        code = _strip_c_comments(BMBATTLE_SRC.read_text(encoding="utf-8"))
        self.assertIn("#if FE8_EXPANSION_MECHANICS_HOOKS", code)
        self.assertIn("ExpansionMechanicsApplyBattleStats", code)
        # The apply call must sit inside the gated region, before an #endif.
        gated = re.search(
            r"#if FE8_EXPANSION_MECHANICS_HOOKS(.*?)#endif", code, flags=re.DOTALL
        )
        self.assertIsNotNone(gated, "seam must be wrapped in #if/#endif")
        self.assertIn("ExpansionMechanicsApplyBattleStats", gated.group(1))

    def test_disabled_bmbattle_object_has_no_mechanics_reference(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, obj = _compile(tmp, BMBATTLE_SRC, "bmbattle_default.o")
            self.assertEqual(rc, 0, "compiling bmbattle.c (default) failed:\n" + out)
            refs = _referenced_symbol_names(obj)
        mechanics_refs = [name for name in refs if "ExpansionMechanics" in name]
        self.assertEqual(
            mechanics_refs,
            [],
            "default (disabled) bmbattle.o must not reference the mechanics seam; "
            "found: %r" % mechanics_refs,
        )

    def test_enabled_bmbattle_object_references_the_seam(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, obj = _compile(
                tmp, BMBATTLE_SRC, "bmbattle_enabled.o",
                defines=["FE8_EXPANSION_MECHANICS_HOOKS=1"],
            )
            self.assertEqual(rc, 0, "compiling bmbattle.c (enabled) failed:\n" + out)
            refs = _referenced_symbol_names(obj)
        self.assertIn("ExpansionMechanicsApplyBattleStats", refs)


class MechanicsBuildWiringTests(unittest.TestCase):
    """C89/AAPCS shape and modern.mk/Makefile wiring."""

    def test_source_and_header_exist_and_are_globbed(self):
        self.assertTrue(MECHANICS_SRC.is_file(), "src/expansion_mechanics.c must exist")
        self.assertTrue(MECHANICS_HEADER.is_file(), "include/expansion_mechanics.h must exist")
        # Auto-globbed by both build lanes via src/*.c.
        self.assertIn(MECHANICS_SRC, list((REPO_ROOT / "src").glob("*.c")))

    def test_modern_mk_wires_the_flag_defines(self):
        modern_mk = (REPO_ROOT / "modern.mk").read_text(encoding="utf-8")
        self.assertIn("-DFE8_EXPANSION_MECHANICS_HOOKS=$(EXPANSION_MECHANICS_HOOKS)", modern_mk)
        self.assertIn("-DFE8_EXPANSION_MECHANICS_SAMPLE=$(EXPANSION_MECHANICS_SAMPLE)", modern_mk)

    def test_c89_shape_has_no_declaration_after_statement(self):
        _skip_if_no_host_compiler()
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for defs in ([], ["FE8_EXPANSION_MECHANICS_HOOKS=1",
                              "FE8_EXPANSION_MECHANICS_SAMPLE=1"]):
                rc, out, _ = _compile(
                    tmp, MECHANICS_SRC, "c89.o", defines=defs,
                    extra=["-std=gnu89", "-Werror=declaration-after-statement",
                           "-Werror=implicit-function-declaration",
                           "-Werror=implicit-int"],
                )
                self.assertEqual(rc, 0, "C89-shape compile failed (defs=%r):\n%s" % (defs, out))

    def test_no_new_line_comments_in_shared_c(self):
        for path in (MECHANICS_SRC, MECHANICS_HEADER):
            text = path.read_text(encoding="utf-8")
            stripped = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
            stripped = re.sub(r'"(\\.|[^"\\])*"', ' ', stripped)
            self.assertNotIn("//", stripped, "%s must use only /* */ comments" % path.name)

    def test_arm_aapcs_compile(self):
        if ARM_CC is None:
            raise unittest.SkipTest("arm-none-eabi-gcc not available")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obj = Path(tmp) / "mech_arm.o"
            cmd = [ARM_CC, "-mthumb", "-mcpu=arm7tdmi", "-mabi=aapcs", "-std=gnu89",
                   "-c", "-w"] + _include_flags() + [
                "-DFE8_EXPANSION_MECHANICS_HOOKS=1",
                "-DFE8_EXPANSION_MECHANICS_SAMPLE=1",
                str(MECHANICS_SRC), "-o", str(obj)]
            proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             "arm AAPCS compile failed:\n" + proc.stdout + proc.stderr)
            arm_nm = shutil.which("arm-none-eabi-nm")
            if arm_nm is not None:
                syms = subprocess.run([arm_nm, str(obj)], capture_output=True, text=True).stdout
                self.assertIn("ExpansionMechanicsApplyBattleStats", syms)
                self.assertIn("gExpansionMechanicsProbe", syms)


if __name__ == "__main__":
    unittest.main()
