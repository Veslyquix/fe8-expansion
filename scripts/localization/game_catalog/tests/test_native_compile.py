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
        try:
            subprocess.run(
                ["cc", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest("no host cc available")

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


if __name__ == "__main__":
    unittest.main()
