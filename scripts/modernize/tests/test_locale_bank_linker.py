"""Synthetic GNU ld coverage for linker/expansion.ld's upper locale bank."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LINKER_SCRIPT = ROOT / "linker" / "expansion.ld"
SCRATCH_ROOT = ROOT / "build" / "test-scratch" / "locale-bank-linker"
START_MARKER = "/* === UPPER ROM: locale bank (32 MiB profiles only) === */"
END_MARKER = "/* === END UPPER ROM LOCALE BANK === */"


class LocaleBankLinkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assembler = shutil.which("arm-none-eabi-as")
        cls.linker = shutil.which("arm-none-eabi-ld")
        cls.objdump = shutil.which("arm-none-eabi-objdump")
        cls.nm = shutil.which("arm-none-eabi-nm")
        if not all((cls.assembler, cls.linker, cls.objdump, cls.nm)):
            raise unittest.SkipTest("arm-none-eabi binutils are not available")

    def setUp(self):
        self.scratch = SCRATCH_ROOT / self._testMethodName
        shutil.rmtree(self.scratch, ignore_errors=True)
        self.scratch.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.scratch, ignore_errors=True)

    def _locale_block(self) -> str:
        text = LINKER_SCRIPT.read_text(encoding="utf-8")
        self.assertIn(START_MARKER, text)
        self.assertIn(END_MARKER, text)
        body = text.split(START_MARKER, 1)[1].split(END_MARKER, 1)[0]
        return f"{START_MARKER}{body}{END_MARKER}"

    def _link(self, *, rom_size: str, locale_bytes: int):
        locale_input = ""
        if locale_bytes:
            locale_input = (
                '\n.section .locale_data.fixture,"a",%progbits\n'
                f".space {locale_bytes}, 0x5A\n"
            )
        assembly = (
            ".syntax unified\n"
            ".thumb\n"
            '.section .text.Init,"ax",%progbits\n'
            ".global Init\n"
            ".type Init, %function\n"
            "Init:\n"
            "    bx lr\n"
            '.section .rodata.fixture,"a",%progbits\n'
            ".word 0x12345678\n"
            f"{locale_input}"
        )
        source = self.scratch / "fixture.s"
        obj = self.scratch / "fixture.o"
        elf = self.scratch / "fixture.elf"
        map_path = self.scratch / "fixture.map"
        script = self.scratch / "fixture.ld"
        source.write_text(assembly, encoding="utf-8")
        script.write_text(
            "OUTPUT_ARCH(arm)\n"
            "MEMORY\n"
            "{\n"
            "    rom : ORIGIN = 0x08000000, LENGTH = __rom_size\n"
            "}\n"
            "ENTRY(Init)\n"
            "SECTIONS\n"
            "{\n"
            "    .text 0x08000000 : { *(.text .text.*) } > rom\n"
            "    .rodata : { *(.rodata .rodata.*) } > rom\n"
            f"    {self._locale_block()}\n"
            "}\n",
            encoding="utf-8",
        )
        subprocess.run(
            [self.assembler, "-mcpu=arm7tdmi", "-mthumb", "-o", obj, source],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        result = subprocess.run(
            [
                self.linker,
                f"--defsym=__rom_size={rom_size}",
                "-T", script,
                "-Map", map_path,
                "-o", elf,
                obj,
            ],
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return result, elf

    def _symbols(self, elf: Path) -> dict[str, int]:
        result = subprocess.run(
            [self.nm, "-n", elf],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        symbols = {}
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) == 3:
                symbols[fields[2]] = int(fields[0], 16)
        return symbols

    def _sections(self, elf: Path) -> dict[str, tuple[int, int]]:
        result = subprocess.run(
            [self.objdump, "-h", elf],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        sections = {}
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 4 and fields[0].isdigit():
                sections[fields[1]] = (int(fields[2], 16), int(fields[3], 16))
        return sections

    def test_empty_locale_bank_is_harmless_at_16m(self):
        result, elf = self._link(rom_size="0x01000000", locale_bytes=0)
        self.assertEqual(result.returncode, 0, result.stdout)
        symbols = self._symbols(elf)
        self.assertEqual(symbols["__locale_bank_start"], 0x09000000)
        self.assertEqual(symbols["__locale_bank_end"], 0x09000000)
        self.assertEqual(symbols["__locale_bank_size"], 0)

    def test_nonempty_locale_bank_is_rejected_at_16m(self):
        result, _elf = self._link(rom_size="0x01000000", locale_bytes=4)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Locale data requires MODERN_ROM_SIZE=32M", result.stdout)

    def test_bounded_locale_bank_links_at_32m_and_stays_upper(self):
        result, elf = self._link(rom_size="0x02000000", locale_bytes=4)
        self.assertEqual(result.returncode, 0, result.stdout)
        symbols = self._symbols(elf)
        sections = self._sections(elf)
        self.assertLess(sections[".rodata"][1], 0x09000000)
        self.assertEqual(sections[".locale_data"], (4, 0x09000000))
        self.assertEqual(symbols["__locale_bank_start"], 0x09000000)
        self.assertEqual(symbols["__locale_bank_end"], 0x09000004)
        self.assertEqual(symbols["__locale_bank_size"], 4)
