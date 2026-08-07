"""Host-native strict UTF-8 and compact CJK renderer tests."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEST_DIR = Path(__file__).resolve().parent
BUILD_DIR = TEST_DIR / ".text_renderer_host_build"
HOST_INCLUDE = TEST_DIR / "renderer_host_include"
DATA_SOURCE = ROOT / "src" / "data" / "localized_font_data.c"
EXPECTED_LOCALE_DATA_SIZE = 594_504


class TextRendererNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "nm", "size", "objdump"):
            if shutil.which(tool) is None:
                raise unittest.SkipTest(f"no host {tool!r} tool available")

        cls.preproc = ROOT / "tools" / "preproc" / "preproc"
        if not cls.preproc.is_file():
            result = subprocess.run(
                ["make", "-C", str(ROOT / "tools" / "preproc")],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if result.returncode != 0:
                raise unittest.SkipTest(
                    f"could not build repository preproc tool:\n{result.stdout}"
                )

    def setUp(self):
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        BUILD_DIR.mkdir()
        self.preprocessed_data = BUILD_DIR / "localized_font_data.pre.c"
        result = subprocess.run(
            [str(self.preproc), str(DATA_SOURCE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.preprocessed_data.write_text(result.stdout, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    def _compile(self, arguments):
        result = subprocess.run(
            [
                "cc",
                "-std=c89",
                "-pedantic-errors",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fcf-protection=none",
                "-I",
                str(HOST_INCLUDE),
                "-I",
                str(ROOT / "include"),
            ]
            + [str(argument) for argument in arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def _assert_zero_object(self, object_path):
        nm_result = subprocess.run(
            ["nm", "--defined-only", str(object_path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(nm_result.returncode, 0, nm_result.stdout)
        self.assertEqual(nm_result.stdout.strip(), "")

        size_result = subprocess.run(
            ["size", str(object_path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(size_result.returncode, 0, size_result.stdout)
        fields = size_result.stdout.splitlines()[-1].split()
        self.assertEqual([int(value) for value in fields[:3]], [0, 0, 0])

    def test_disabled_profiles_emit_zero_runtime_and_asset_objects(self):
        profiles = (
            ("legacy", []),
            ("modern-english", ["-DMODERN=1", "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x1u"]),
            ("modern-qps", ["-DMODERN=1", "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x81u"]),
        )
        sources = (
            ROOT / "src" / "text_utf8.c",
            ROOT / "src" / "localized_font.c",
            self.preprocessed_data,
        )
        for profile, defines in profiles:
            for source in sources:
                with self.subTest(profile=profile, source=source.name):
                    output = BUILD_DIR / f"{profile}-{source.stem}.o"
                    self._compile(defines + ["-c", source, "-o", output])
                    self._assert_zero_object(output)

    def test_cjk_runtime_assets_and_iterator(self):
        binary = BUILD_DIR / "text_renderer_host_test"
        linker_script = BUILD_DIR / "locale_data.ld"
        linker_script.write_text(
            "SECTIONS { .locale_data : { *(.locale_data .locale_data.*) } }\n"
            "INSERT AFTER .rodata;\n",
            encoding="ascii",
        )
        self._compile(
            [
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x7u",
                ROOT / "src" / "text_utf8.c",
                ROOT / "src" / "localized_font.c",
                self.preprocessed_data,
                TEST_DIR / "text_renderer_host_test.c",
                "-no-pie",
                f"-Wl,-T,{linker_script}",
                "-o",
                binary,
            ]
        )

        run_result = subprocess.run(
            [str(binary)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(run_result.returncode, 0, run_result.stdout)
        self.assertEqual(run_result.stdout.strip(), "text_renderer_host_test: ok")

        sections = subprocess.run(
            ["objdump", "-h", str(binary)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(sections.returncode, 0, sections.stdout)
        locale_rows = [
            line.split()
            for line in sections.stdout.splitlines()
            if len(line.split()) >= 3 and line.split()[1] == ".locale_data"
        ]
        self.assertEqual(len(locale_rows), 1, sections.stdout)
        self.assertEqual(int(locale_rows[0][2], 16), EXPECTED_LOCALE_DATA_SIZE)


if __name__ == "__main__":
    unittest.main()
