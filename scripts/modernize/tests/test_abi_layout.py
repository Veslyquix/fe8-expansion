"""Compile-time ABI layout assertions for core engine structures.

Verifies that sizeof, offsetof, and _Alignof for Proc, Unit, PlaySt, BmSt,
save, and data-table structures match documented header-comment offsets in
all four modern build cells (debug/release x AAPCS/APCS-GNU).

Every expected value was established by a four-cell compiler probe using
arm-none-eabi-gcc 13.2.1 against the real project headers.  The assertions
are compiled — not executed — so no target hardware is needed.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class CoreABILayoutTests(unittest.TestCase):

    # -- helpers (same conventions as test_modern_build.py) -----------------

    def make(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "--no-print-directory", *arguments],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def tool_overrides(self) -> list[str] | None:
        prefix = os.environ.get("PREFIX", "arm-none-eabi-")
        root = os.environ.get("MODERN_TOOLCHAIN_ROOT", "")
        cc = os.environ.get("MODERN_CC", "")
        if not cc and root:
            cc = str(Path(root) / "bin" / f"{prefix}gcc")
        if not cc:
            cc = shutil.which(f"{prefix}gcc") or ""

        objdump = os.environ.get("MODERN_OBJDUMP", "")
        if not objdump:
            objdump = shutil.which(f"{prefix}objdump") or ""

        if not cc or not objdump:
            return None

        overrides = [f"MODERN_CC={cc}", f"MODERN_OBJDUMP={objdump}"]
        for variable in ("MODERN_BINUTILS_DIR", "MODERN_NEWLIB_INCLUDE"):
            value = os.environ.get(variable)
            if value:
                overrides.append(f"{variable}={value}")
        return overrides

    # -- the test -----------------------------------------------------------

    # The C probe source.  Each _Static_assert value comes from the four-cell
    # compiler probe run against the real headers; all four cells returned
    # identical results.
    _PROBE_SOURCE = textwrap.dedent("""\
        #include <stddef.h>
        #include "global.h"
        #include "proc.h"
        #include "bmunit.h"
        #include "bmsave.h"
        #include "hardware.h"

        /* ---- Proc system ---- */
        _Static_assert(sizeof(struct Proc) == 0x6C,
                       "Proc size");
        _Static_assert(sizeof(struct ProcCmd) == 0x8,
                       "ProcCmd size");
        _Static_assert(offsetof(struct Proc, proc_idleCb) == 0x0C,
                       "Proc.idleCb offset");
        _Static_assert(offsetof(struct Proc, proc_name) == 0x10,
                       "Proc.name offset");
        _Static_assert(offsetof(struct Proc, proc_parent) == 0x14,
                       "Proc.parent offset");
        _Static_assert(offsetof(struct Proc, proc_sleepTime) == 0x24,
                       "Proc.sleepTime offset");
        _Static_assert(offsetof(struct Proc, proc_mark) == 0x26,
                       "Proc.mark offset");
        _Static_assert(offsetof(struct Proc, proc_lockCnt) == 0x28,
                       "Proc.lockCnt offset");
        _Static_assert(offsetof(struct Proc, x) == 0x2C,
                       "Proc.x offset");
        _Static_assert(offsetof(struct Proc, ptr) == 0x54,
                       "Proc.ptr offset");
        _Static_assert(offsetof(struct Proc, unk64) == 0x64,
                       "Proc.unk64 offset");
        _Static_assert(_Alignof(struct Proc) == 4,
                       "Proc alignment");

        /* ---- Unit system ---- */
#ifdef DEBUFFS_EXIST
        _Static_assert(sizeof(struct Unit) == 0x4C,
                       "Unit size");
        _Static_assert(offsetof(struct Unit, debuffs) == 0x48,
                       "Unit.debuffs offset");
#else
        _Static_assert(sizeof(struct Unit) == 0x48,
                       "Unit size");
#endif
        _Static_assert(offsetof(struct Unit, level) == 0x08,
                       "Unit.level offset");
        _Static_assert(offsetof(struct Unit, state) == 0x0C,
                       "Unit.state offset");
        _Static_assert(offsetof(struct Unit, xPos) == 0x10,
                       "Unit.xPos offset");
        _Static_assert(offsetof(struct Unit, items) == 0x1E,
                       "Unit.items offset");
        _Static_assert(offsetof(struct Unit, ranks) == 0x28,
                       "Unit.ranks offset");
        _Static_assert(offsetof(struct Unit, pMapSpriteHandle) == 0x3C,
                       "Unit.pMapSpriteHandle offset");
        _Static_assert(offsetof(struct Unit, ai_config) == 0x40,
                       "Unit.ai_config offset");
        _Static_assert(sizeof(struct UnitDefinition) == 0x14,
                       "UnitDefinition size");
        _Static_assert(offsetof(struct UnitDefinition, redas) == 0x08,
                       "UnitDefinition.redas offset");
        _Static_assert(_Alignof(struct UnitDefinition) == 4,
                       "UnitDefinition alignment");
        _Static_assert(sizeof(struct CharacterData) == 0x34,
                       "CharacterData size");
        _Static_assert(sizeof(struct ClassData) == 0x54,
                       "ClassData size");

        /* ---- Game state and save ---- */
        _Static_assert(sizeof(struct PlaySt) == 0x4C,
                       "PlaySt size");
        _Static_assert(sizeof(struct PlaySt_30) == 0x10,
                       "PlaySt_30 size");
        _Static_assert(sizeof(struct PlaySt_OptionBits) == 0x8,
                       "PlaySt_OptionBits size");
        _Static_assert(offsetof(struct PlaySt, partyGoldAmount) == 0x08,
                       "PlaySt.partyGoldAmount offset");
        _Static_assert(offsetof(struct PlaySt, chapterIndex) == 0x0E,
                       "PlaySt.chapterIndex offset");
        _Static_assert(offsetof(struct PlaySt, config) == 0x40,
                       "PlaySt.config offset");
        _Static_assert(sizeof(struct BmSt) == 0x40,
                       "BmSt size");
        _Static_assert(offsetof(struct BmSt, camera) == 0x0C,
                       "BmSt.camera offset");
        _Static_assert(sizeof(struct SaveBlockInfo) == 0x10,
                       "SaveBlockInfo size");
    """)

    def test_core_abi_layout_in_all_modern_modes(self):
        """All 35 layout assertions must compile in every debug/release x ABI cell."""
        overrides = self.tool_overrides()
        if overrides is None:
            self.skipTest("arm-none-eabi GCC and objdump are not available")

        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "core_abi_layout.c"
            output_root = temporary_path / "abi-layout-objects"
            source.write_text(self._PROBE_SOURCE, encoding="utf-8")

            for config in ("debug", "release"):
                for abi in ("aapcs", "apcs-gnu"):
                    result = self.make(
                        ROOT,
                        "expansion-modern-cohort",
                        f"MODERN_CONFIG={config}",
                        f"MODERN_ABI={abi}",
                        f"MODERN_BUILD_ROOT={output_root}",
                        f"MODERN_COHORT_SOURCES={source}",
                        "MODERN_COHORT_ASM_SOURCES=",
                        *overrides,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"{config}/{abi} core ABI layout probe failed:\n"
                        f"{result.stdout}",
                    )

            objects = list(output_root.rglob("*.o"))
            deps = list(output_root.rglob("*.d"))
            self.assertEqual(
                len(objects), 4,
                f"expected 4 objects (one per cell), got {len(objects)}",
            )
            self.assertEqual(
                len(deps), 4,
                f"expected 4 dependency files, got {len(deps)}",
            )


if __name__ == "__main__":
    unittest.main()
