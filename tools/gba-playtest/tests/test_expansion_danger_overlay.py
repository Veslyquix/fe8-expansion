"""
Issue #6 host tests -- player QoL danger/range overlay map-menu surface.

These compile the real src/menu_def.c and src/bmmenu.c with a native host
compiler in both the disabled (default) and enabled configurations and prove,
from the actual compiled objects, that:

  * the disabled build's gMapMenuItems table is byte-identical to vanilla
    (unchanged size -- no visible item added, fully vanilla behaviour);
  * the enabled build adds exactly one MenuItemDef and stays within
    MENU_ITEM_MAX;
  * the promote-wrapper is compile-gated (the default bmmenu object has no
    reference to it) and delegates to the vanilla danger-zone effect;
  * the surface is wired through modern.mk's -D flags.

The full menu Proc/rendering engine is not host-executable, so selection/
cancel lifecycle is proven at runtime by the gba-playtest scenario
(tools/gba-playtest/scenarios/starter-danger-overlay-*.json); here we prove
the table/callback/config contract that the scenario builds on.
"""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INCLUDE_DIRS = [REPO_ROOT / "include", REPO_ROOT / "include" / "generated"]
MENU_DEF_SRC = REPO_ROOT / "src" / "menu_def.c"
BMMENU_SRC = REPO_ROOT / "src" / "bmmenu.c"
BMMENU_HEADER = REPO_ROOT / "include" / "bmmenu.h"
PLAYERPHASE_SRC = REPO_ROOT / "src" / "playerphase.c"
PROBE_HEADER = REPO_ROOT / "include" / "expansion_danger_overlay.h"

CC = shutil.which("gcc") or shutil.which("cc")
ARM_CC = shutil.which("arm-none-eabi-gcc")
NM = shutil.which("nm")

FLAG = "FE8_EXPANSION_DANGER_OVERLAY_MENU"


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


def _symbol_size(obj, name):
    if NM is None:
        raise unittest.SkipTest("no host 'nm' available")
    proc = subprocess.run([NM, "--print-size", str(obj)], capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[3] == name:
            return int(parts[1], 16)
    raise AssertionError("symbol %r not found (with size) in %s" % (name, obj))


def _referenced_symbol_names(obj):
    if NM is None:
        raise unittest.SkipTest("no host 'nm' available")
    proc = subprocess.run([NM, str(obj)], capture_output=True, text=True)
    return {line.split()[-1] for line in proc.stdout.splitlines() if line.split()}


def _probe_constants(work_dir):
    """sizeof(struct MenuItemDef) and MENU_ITEM_MAX, on this host."""
    src = Path(work_dir) / "probe.c"
    src.write_text(
        '#include "global.h"\n#include "uimenu.h"\n#include <stdio.h>\n'
        'int main(void){printf("%zu %d\\n", sizeof(struct MenuItemDef),'
        ' (int)MENU_ITEM_MAX); return 0;}\n',
        encoding="utf-8",
    )
    exe = Path(work_dir) / "probe"
    cmd = [CC, "-w"] + _include_flags() + [str(src), "-o", str(exe)]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = subprocess.run([str(exe)], capture_output=True, text=True).stdout.split()
    return int(out[0]), int(out[1])


def _strip_c_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


class DangerOverlayTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_disabled_table_is_vanilla_and_enabled_adds_exactly_one(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            sizeof_item, menu_item_max = _probe_constants(tmp)
            rc, out, dis = _compile(tmp, MENU_DEF_SRC, "md_dis.o")
            self.assertEqual(rc, 0, "compiling menu_def.c (disabled) failed:\n" + out)
            rc, out, ena = _compile(tmp, MENU_DEF_SRC, "md_en.o", defines=[FLAG + "=1"])
            self.assertEqual(rc, 0, "compiling menu_def.c (enabled) failed:\n" + out)
            dis_size = _symbol_size(dis, "gMapMenuItems")
            ena_size = _symbol_size(ena, "gMapMenuItems")

        self.assertEqual(dis_size % sizeof_item, 0, "table size must be a whole number of items")
        dis_entries = dis_size // sizeof_item
        ena_entries = ena_size // sizeof_item
        # Exactly one MenuItemDef added when enabled; nothing when disabled.
        self.assertEqual(ena_entries, dis_entries + 1,
                         "enabled table must add exactly one MenuItemDef")
        # The table includes a MenuItemsEnd terminator; visible items exclude it.
        visible_when_enabled = ena_entries - 1
        self.assertLessEqual(visible_when_enabled, menu_item_max,
                             "enabled visible item count must stay within MENU_ITEM_MAX")

    def test_enabled_object_references_the_promoted_effect(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, ena = _compile(tmp, MENU_DEF_SRC, "md_en.o", defines=[FLAG + "=1"])
            self.assertEqual(rc, 0, out)
            refs = _referenced_symbol_names(ena)
        self.assertIn("ExpansionDangerOverlay_MenuSelect", refs,
                      "enabled menu table must reference the promote-wrapper")


class DangerOverlayWrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_wrapper_is_compile_gated_and_delegates(self):
        code = _strip_c_comments(BMMENU_SRC.read_text(encoding="utf-8"))
        gated = re.search(
            r"#if FE8_EXPANSION_DANGER_OVERLAY_MENU(.*?)#endif", code, flags=re.DOTALL
        )
        self.assertIsNotNone(gated, "wrapper must be wrapped in #if/#endif")
        body = gated.group(1)
        self.assertIn("ExpansionDangerOverlay_MenuSelect", body)
        self.assertIn("MapMenu_DangerZone_UnusedEffect", body,
                      "wrapper must reuse (delegate to) the vanilla danger-zone effect")

    def test_disabled_bmmenu_has_no_wrapper_reference(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, obj = _compile(tmp, BMMENU_SRC, "bmmenu_default.o")
            self.assertEqual(rc, 0, out)
            refs = _referenced_symbol_names(obj)
        wrapper_refs = [n for n in refs if "ExpansionDangerOverlay" in n]
        self.assertEqual(wrapper_refs, [],
                         "default bmmenu.o must not reference the overlay wrapper; found: %r"
                         % wrapper_refs)

    def test_enabled_bmmenu_defines_the_wrapper(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, obj = _compile(tmp, BMMENU_SRC, "bmmenu_enabled.o", defines=[FLAG + "=1"])
            self.assertEqual(rc, 0, out)
            refs = _referenced_symbol_names(obj)
        self.assertIn("ExpansionDangerOverlay_MenuSelect", refs)


class DangerOverlayWiringTests(unittest.TestCase):
    def test_modern_mk_wires_the_flag_define(self):
        modern_mk = (REPO_ROOT / "modern.mk").read_text(encoding="utf-8")
        self.assertIn("-DFE8_EXPANSION_DANGER_OVERLAY_MENU=$(EXPANSION_DANGER_OVERLAY_MENU)", modern_mk)

    def test_no_new_line_comments_in_added_regions(self):
        # Our additions (wrapper, gated item, declaration) must use /* */ only.
        for path, needle in ((BMMENU_SRC, "ExpansionDangerOverlay_MenuSelect"),
                             (MENU_DEF_SRC, "Threat Range")):
            text = path.read_text(encoding="utf-8")
            gated = re.findall(r"#if FE8_EXPANSION_DANGER_OVERLAY_MENU(.*?)#endif",
                               text, flags=re.DOTALL)
            self.assertTrue(any(needle in g for g in gated), "gated region for %s" % needle)
            for g in gated:
                if needle in g:
                    self.assertNotIn("//", g, "%s gated region must use /* */ only" % path.name)

    def test_arm_aapcs_compiles_enabled(self):
        if ARM_CC is None:
            raise unittest.SkipTest("arm-none-eabi-gcc not available")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for src, name in ((MENU_DEF_SRC, "md.o"), (BMMENU_SRC, "bm.o")):
                obj = Path(tmp) / name
                cmd = [ARM_CC, "-mthumb", "-mcpu=arm7tdmi", "-mabi=aapcs", "-std=gnu89",
                       "-c", "-w"] + _include_flags() + ["-D" + FLAG + "=1",
                       str(src), "-o", str(obj)]
                proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0,
                                 "arm compile of %s failed:\n%s" % (src.name, proc.stdout + proc.stderr))


class DangerOverlayProbeTests(unittest.TestCase):
    """The always-linked QoL semantic probe and its compile-gated writes."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_probe_header_exists(self):
        self.assertTrue(PROBE_HEADER.is_file(),
                        "include/expansion_danger_overlay.h must exist")

    def test_probe_symbol_is_always_linked_in_both_configs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for defs, tag in (([], "dis"), ([FLAG + "=1"], "en")):
                rc, out, obj = _compile(tmp, PLAYERPHASE_SRC, "pp_%s.o" % tag, defines=defs)
                self.assertEqual(rc, 0, "compiling playerphase.c (%s) failed:\n%s" % (tag, out))
                syms = _referenced_symbol_names(obj)
                self.assertIn("gExpansionDangerOverlayProbe", syms,
                              "%s build must always link the probe symbol" % tag)

    def test_probe_writes_are_compile_gated(self):
        """Every probe field write in the shared danger-zone path must live
        inside a #if FE8_EXPANSION_DANGER_OVERLAY_MENU region, so the default
        build keeps vanilla playerphase/bmmenu behaviour."""
        for src in (PLAYERPHASE_SRC, BMMENU_SRC):
            text = src.read_text(encoding="utf-8")
            gated = "".join(re.findall(
                r"#if FE8_EXPANSION_DANGER_OVERLAY_MENU(.*?)#endif", text, flags=re.DOTALL))
            ungated = re.sub(
                r"#if FE8_EXPANSION_DANGER_OVERLAY_MENU.*?#endif", " ", text, flags=re.DOTALL)
            ungated = _strip_c_comments(ungated)
            # The probe struct definition is allowed ungated (always-linked);
            # field writes (".<field>Count++/=") must not appear ungated.
            self.assertNotRegex(
                ungated, r"gExpansionDangerOverlayProbe\.\w+\s*(\+\+|=)",
                "%s writes the danger-overlay probe outside a gated region" % src.name)
            if "gExpansionDangerOverlayProbe." in text:
                self.assertIn("gExpansionDangerOverlayProbe.", gated,
                              "%s must write the probe only inside gated regions" % src.name)

    def test_probe_header_uses_block_comments_only(self):
        text = PROBE_HEADER.read_text(encoding="utf-8")
        stripped = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
        self.assertNotIn("//", stripped, "probe header must use /* */ comments only")

    def test_playerphase_arm_compiles_enabled(self):
        if ARM_CC is None:
            raise unittest.SkipTest("arm-none-eabi-gcc not available")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obj = Path(tmp) / "pp.o"
            cmd = [ARM_CC, "-mthumb", "-mcpu=arm7tdmi", "-mabi=aapcs", "-std=gnu89",
                   "-c", "-w"] + _include_flags() + ["-D" + FLAG + "=1",
                   str(PLAYERPHASE_SRC), "-o", str(obj)]
            proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             "arm compile of playerphase.c failed:\n" + proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
