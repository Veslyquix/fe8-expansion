"""Host-native tests for UTF-8 dialogue, CG text, and help-box consumers."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEST_DIR = Path(__file__).resolve().parent
BUILD_DIR = TEST_DIR / ".text_consumer_host_build"


class TextConsumerNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("cc") is None:
            raise unittest.SkipTest("no host C compiler available")

    def setUp(self):
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        BUILD_DIR.mkdir()

    def tearDown(self):
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    def _run(self, command):
        result = subprocess.run(
            [str(value) for value in command],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def test_dialogue_cg_and_help_consumers(self):
        common = [
            "cc",
            "-std=gnu89",
            "-Wall",
            "-Wextra",
            "-Werror=implicit-function-declaration",
            "-Werror=declaration-after-statement",
            "-Wno-int-to-pointer-cast",
            "-Wno-pointer-to-int-cast",
            "-Wno-address-of-packed-member",
            "-no-pie",
            "-funsigned-char",
            "-ffunction-sections",
            "-fdata-sections",
            "-DMODERN=1",
            "-DNONMATCHING=1",
            "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x07u",
            "-DFE8_TEXT_CONSUMER_HOST_TEST=1",
            "-I",
            ROOT / "include",
        ]
        objects = []
        for source in ("scene.c", "cgtext.c", "helpbox.c"):
            output = BUILD_DIR / f"{Path(source).stem}.o"
            self._run(
                common
                + [
                    "-c",
                    ROOT / "src" / source,
                    "-o",
                    output,
                ]
            )
            objects.append(output)

        binary = BUILD_DIR / "text_consumer_host_test"
        self._run(
            common
            + [
                ROOT / "src" / "text_utf8.c",
                TEST_DIR / "text_consumer_host_test.c",
            ]
            + objects
            + [
                "-Wl,--gc-sections",
                "-Wl,--unresolved-symbols=ignore-all",
                "-o",
                binary,
            ]
        )
        result = self._run([binary])
        self.assertEqual(result.stdout.strip(), "text_consumer_host_test: ok")

    def test_reviewed_consumer_functions(self):
        common = [
            "cc",
            "-std=gnu89",
            "-Wall",
            "-Wextra",
            "-Werror=implicit-function-declaration",
            "-Werror=declaration-after-statement",
            "-Wno-int-to-pointer-cast",
            "-Wno-pointer-to-int-cast",
            "-Wno-address-of-packed-member",
            "-Wno-unused-parameter",
            "-no-pie",
            "-fsigned-char",
            "-ffunction-sections",
            "-fdata-sections",
            "-DMODERN=1",
            "-DNONMATCHING=1",
            "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x07u",
            "-DFE8_TEXT_CONSUMER_HOST_TEST=1",
            "-I",
            ROOT / "include",
        ]
        objects = []
        for source in (
            "bmio.c",
            "opinfo.c",
            "classchg-sel.c",
            "bmsave-multiarena.c",
            "sio_tactician.c",
            "localized_font.c",
        ):
            output = BUILD_DIR / f"{Path(source).stem}.reviewed.o"
            self._run(
                common
                + [
                    "-c",
                    ROOT / "src" / source,
                    "-o",
                    output,
                ]
            )
            objects.append(output)

        font_symbols = (
            (
                "gLocalizedFontJaSystemCodepoints",
                ROOT / "graphics/fonts/cjk/ja.system.codepoints.bin",
            ),
            (
                "gLocalizedFontJaSystemWidths",
                ROOT / "graphics/fonts/cjk/ja.system.widths.bin",
            ),
            (
                "gLocalizedFontJaSystemBitmaps",
                ROOT / "graphics/fonts/cjk/ja.system.glyphs.2bpp",
            ),
            (
                "gLocalizedFontJaTalkCodepoints",
                ROOT / "graphics/fonts/cjk/ja.talk.codepoints.bin",
            ),
            (
                "gLocalizedFontJaTalkWidths",
                ROOT / "graphics/fonts/cjk/ja.talk.widths.bin",
            ),
            (
                "gLocalizedFontJaTalkBitmaps",
                ROOT / "graphics/fonts/cjk/ja.talk.glyphs.2bpp",
            ),
            (
                "gLocalizedFontZhHansSystemCodepoints",
                ROOT / "graphics/fonts/cjk/zh-Hans.system.codepoints.bin",
            ),
            (
                "gLocalizedFontZhHansSystemWidths",
                ROOT / "graphics/fonts/cjk/zh-Hans.system.widths.bin",
            ),
            (
                "gLocalizedFontZhHansSystemBitmaps",
                ROOT / "graphics/fonts/cjk/zh-Hans.system.glyphs.2bpp",
            ),
            (
                "gLocalizedFontZhHansTalkCodepoints",
                ROOT / "graphics/fonts/cjk/zh-Hans.talk.codepoints.bin",
            ),
            (
                "gLocalizedFontZhHansTalkWidths",
                ROOT / "graphics/fonts/cjk/zh-Hans.talk.widths.bin",
            ),
            (
                "gLocalizedFontZhHansTalkBitmaps",
                ROOT / "graphics/fonts/cjk/zh-Hans.talk.glyphs.2bpp",
            ),
        )
        font_data_lines = [".section .rodata", ".balign 4"]
        font_data_lines.extend(
            f'.globl {symbol}\n{symbol}:\n.incbin "{path}"'
            for symbol, path in font_symbols
        )
        font_data_lines.extend(
            [".section .note.GNU-stack,\"\",@progbits", ""]
        )
        font_data = BUILD_DIR / "localized_font_host_data.S"
        font_data.write_text("\n".join(font_data_lines), encoding="utf-8")
        font_data_object = BUILD_DIR / "localized_font_host_data.o"
        self._run(["cc", "-c", font_data, "-o", font_data_object])
        objects.append(font_data_object)

        binary = BUILD_DIR / "text_reviewed_consumers_host_test"
        self._run(
            common
            + [
                ROOT / "src" / "text_utf8.c",
                TEST_DIR / "text_reviewed_consumers_host_test.c",
            ]
            + objects
            + [
                "-Wl,--gc-sections",
                "-Wl,--unresolved-symbols=ignore-all",
                "-o",
                binary,
            ]
        )
        result = self._run([binary])
        self.assertEqual(
            result.stdout.strip(), "text_reviewed_consumers_host_test: ok"
        )


if __name__ == "__main__":
    unittest.main()
