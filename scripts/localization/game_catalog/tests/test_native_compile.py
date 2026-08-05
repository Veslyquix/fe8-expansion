import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scripts.localization.game_catalog.build import generate


class NativeCompileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "nm"):
            try:
                subprocess.run(
                    [tool, "--version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            except (OSError, subprocess.CalledProcessError):
                raise unittest.SkipTest(f"no host {tool} available")

    def _tmpdir(self):
        return tempfile.TemporaryDirectory(dir=TEST_DIR)

    def test_generated_header_and_source_compile_as_strict_c89(self):
        with self._tmpdir() as tmp:
            out_dir = Path(tmp)
            written = generate(output_dir=out_dir)
            probe = out_dir / "probe.c"
            probe.write_text(
                "\n".join(
                    (
                        '#include "game_localization_catalog.h"',
                        "const struct GameLocalizationLocaleCatalog *Probe(void)",
                        "{",
                        "    return gGameLocalizationCatalogs[GAME_LOCALIZATION_LOCALE_JA];",
                        "}",
                        "",
                    )
                ),
                encoding="ascii",
            )
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            for path in (written["source"], probe):
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
                        str(TEST_DIR / "host_include"),
                        "-I",
                        str(out_dir),
                        "-fsyntax-only",
                        str(path),
                    ],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                    env=env,
                )
                self.assertEqual(result.returncode, 0, result.stdout)

    def _compile_symbols(self, out_dir: Path, enabled_locales):
        written = generate(output_dir=out_dir, enabled_locales=enabled_locales)
        object_path = out_dir / "catalog.o"
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
                str(TEST_DIR / "host_include"),
                "-I",
                str(out_dir),
                "-c",
                str(written["source"]),
                "-o",
                str(object_path),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        linked_path = out_dir / "catalog-linked.o"
        link_result = subprocess.run(
            ["cc", "-nostdlib", "-r", str(object_path), "-o", str(linked_path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(link_result.returncode, 0, link_result.stdout)
        nm_result = subprocess.run(
            ["nm", "-S", "--defined-only", str(linked_path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(nm_result.returncode, 0, nm_result.stdout)
        symbols = {}
        for line in nm_result.stdout.splitlines():
            fields = line.split()
            if len(fields) == 4:
                symbols[fields[3]] = int(fields[1], 16)
        budget = json.loads(written["budget_json"].read_text(encoding="utf-8"))
        return symbols, budget

    def test_profile_linked_objects_contain_only_enabled_symbols_and_payloads(self):
        with self._tmpdir() as ja_tmp, self._tmpdir() as zh_tmp:
            ja_symbols, ja_budget = self._compile_symbols(Path(ja_tmp), ("ja",))
            zh_symbols, zh_budget = self._compile_symbols(
                Path(zh_tmp), ("zh-Hans",)
            )

            self.assertIn("gGameLocalizationJaCompressedBlob", ja_symbols)
            self.assertNotIn("gGameLocalizationZhHansCompressedBlob", ja_symbols)
            self.assertEqual(
                ja_symbols["gGameLocalizationJaCompressedBlob"],
                ja_budget["locales"]["ja"]["compressed_bytes"],
            )
            self.assertIn("gGameLocalizationZhHansCompressedBlob", zh_symbols)
            self.assertNotIn("gGameLocalizationJaCompressedBlob", zh_symbols)
            self.assertEqual(
                zh_symbols["gGameLocalizationZhHansCompressedBlob"],
                zh_budget["locales"]["zh-Hans"]["compressed_bytes"],
            )


if __name__ == "__main__":
    unittest.main()
