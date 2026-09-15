#!/usr/bin/env python3
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "shiftcheck" / "modern_emit_relocs.sh"
OUT = ROOT / "build" / "shiftcheck" / "modern_relocs.elf"
MAP = ROOT / "build" / "shiftcheck" / "modern_relocs.map"
OBJECTS_LST = ROOT / "build" / "expansion-modern" / "debug" / "aapcs" / "link" / "objects.lst"
ROM = ROOT / "build" / "expansion-modern" / "debug" / "aapcs" / "fireemblem8.gba"
BANIM_SYM = ROOT / "banim" / "data_banim.modern.o.sym.o"


class ModernRelinkTests(unittest.TestCase):
    @staticmethod
    def _candidate_bins():
        prefix = os.environ.get("PREFIX", "arm-none-eabi-")
        seen = set()
        candidates = []

        def add(path):
            if not path:
                return
            resolved = Path(path).expanduser()
            key = str(resolved)
            if key in seen:
                return
            seen.add(key)
            candidates.append(resolved)

        for env_name in ("CC", "MODERN_CC"):
            value = os.environ.get(env_name, "")
            if value:
                add(value)

        root = os.environ.get("MODERN_TOOLCHAIN_ROOT", "")
        if root:
            add(Path(root) / "bin" / f"{prefix}gcc")

        which_cc = shutil.which(f"{prefix}gcc")
        if which_cc:
            add(which_cc)

        add(ROOT / "build" / "toolchain-root" / "usr" / "bin" / f"{prefix}gcc")
        add(ROOT / ".deps" / "arm-toolchain-root" / "usr" / "bin" / f"{prefix}gcc")

        home = Path.home()
        for pattern in (
            f"arm-gnu-toolchain-*/bin/{prefix}gcc",
            f".local/arm-none-eabi-gcc-pkg/usr/bin/{prefix}gcc",
        ):
            for match in home.glob(pattern):
                add(match)

        return [path for path in candidates if path.is_file()]

    @classmethod
    def _toolchain(cls):
        for cc in cls._candidate_bins():
            bindir = cc.parent
            ld = bindir / cc.name.replace("gcc", "ld")
            readelf = bindir / cc.name.replace("gcc", "readelf")
            if ld.is_file() and readelf.is_file():
                return {"CC": str(cc), "LD": str(ld), "READELF": str(readelf)}
        return None

    @classmethod
    def _artifacts_ready(cls):
        return OBJECTS_LST.is_file() and ROM.is_file() and BANIM_SYM.is_file()

    @classmethod
    def _ensure_output(cls):
        if not cls._artifacts_ready():
            raise unittest.SkipTest("modern build artifacts are not available")

        toolchain = cls._toolchain()
        if toolchain is None:
            raise unittest.SkipTest("modern toolchain is not available")

        OUT.parent.mkdir(parents=True, exist_ok=True)
        for path in (OUT, MAP):
            if path.exists():
                path.unlink()

        env = os.environ.copy()
        env.update({"CC": toolchain["CC"], "LD": toolchain["LD"]})
        result = subprocess.run(
            [str(SCRIPT), str(OUT)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stdout)
        return toolchain

    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_relink_produces_abs32_relocations(self):
        toolchain = self._ensure_output()
        result = subprocess.run(
            [toolchain["READELF"], "-r", str(OUT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("R_ARM_ABS32", result.stdout)

    def test_output_contains_expected_sections(self):
        toolchain = self._ensure_output()
        result = subprocess.run(
            [toolchain["READELF"], "-S", str(OUT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        for name in ("ROM", "IWRAM", "ewram_data"):
            self.assertIn(name, result.stdout)


if __name__ == "__main__":
    unittest.main()
