"""Tests for the modern shifted-boot verification pipeline."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "shiftcheck" / "modern_shifted_boot.sh"
MODERN_MAP = ROOT / "build" / "expansion-modern" / "debug" / "aapcs" / "fireemblem8.map"
OBJECTS_LST = ROOT / "build" / "expansion-modern" / "debug" / "aapcs" / "link" / "objects.lst"
BANIM_SYM = ROOT / "banim" / "data_banim.modern.o.sym.o"
LDSCRIPT = ROOT / "linker" / "expansion.ld"


def _has_modern_artifacts():
    return all(p.exists() for p in [MODERN_MAP, OBJECTS_LST, BANIM_SYM, LDSCRIPT])


def _find_toolchain():
    candidates = []
    prefix = os.environ.get("PREFIX", "arm-none-eabi-")
    root = os.environ.get("MODERN_TOOLCHAIN_ROOT")
    if root:
        candidates.append(Path(root) / "bin" / f"{prefix}gcc")
    for variable in ("MODERN_CC", "CC"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value))
    which = shutil.which(f"{prefix}gcc")
    if which:
        candidates.append(Path(which))
    candidates.extend([
        ROOT / "build" / "toolchain-root" / "usr" / "bin" / f"{prefix}gcc",
        ROOT / ".deps" / "arm-toolchain-root" / "usr" / "bin" / f"{prefix}gcc",
    ])

    for cc in candidates:
        if not cc.is_file() or not os.access(cc, os.X_OK):
            continue
        bindir = cc.parent
        tools = {
            "MODERN_CC": cc,
            "MODERN_LD": bindir / f"{prefix}ld",
            "MODERN_OBJCOPY": bindir / f"{prefix}objcopy",
            "MODERN_NM": bindir / f"{prefix}nm",
        }
        if all(path.is_file() and os.access(path, os.X_OK) for path in tools.values()):
            return {name: str(path) for name, path in tools.items()}

    return None


def _has_libmgba():
    try:
        r = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "gba-playtest" / "gba_playtest.py"), "backend-check"],
            capture_output=True, timeout=30,
        )
        return r.returncode == 0
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return False


class TestShiftedBoot(unittest.TestCase):

    def test_script_is_executable(self):
        self.assertTrue(SCRIPT.exists())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_script_fails_without_artifacts(self):
        """Script exits 2 (setup error) when objects list is missing."""
        env = os.environ.copy()
        env["SHIFTCHECK_OBJECTS_LST"] = "/nonexistent/objects.lst"
        r = subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True, text=True, env=env, timeout=10,
        )
        self.assertEqual(r.returncode, 2)
        self.assertIn("error", r.stderr)

    def test_shifted_boot_passes(self):
        """Full pipeline: shifted ROM passes boot behavior verification."""
        toolchain = _find_toolchain()
        if not _has_modern_artifacts() or not toolchain or not _has_libmgba():
            self.skipTest(
                "requires modern build artifacts, arm-none-eabi-gcc, and libmgba"
            )

        nm_result = subprocess.run(
            [toolchain["MODERN_NM"], "-n", "--defined-only",
             str(ROOT / "build" / "expansion-modern" / "debug" / "aapcs"
                 / "fireemblem8.elf")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        symbols = {
            line.split()[-1]: int(line.split()[0], 16)
            for line in nm_result.stdout.splitlines()
            if len(line.split()) >= 3
        }
        if symbols.get("__shift_start") != symbols.get("__shift_end"):
            self.skipTest("existing modern base ELF is not an unshifted fixture")

        env = os.environ.copy()
        env.update(toolchain)
        with tempfile.TemporaryDirectory() as tmp:
            env["SHIFTCHECK_OUTDIR"] = tmp
            r = subprocess.run(
                ["bash", str(SCRIPT)],
                capture_output=True, text=True, env=env, timeout=180,
            )
        self.assertEqual(r.returncode, 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        self.assertIn("SHIFTED BOOT: PASS", r.stdout + r.stderr)
        self.assertIn("SHIFTED TITLE: PASS", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
