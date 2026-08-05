"""Compiles and runs the *real* runtime resolver (src/expansion_locale.c)
against a *real* freshly generated catalog (scripts/localization/generate.py)
with the host's own `cc` (not agbcc/ARM) -- exercising actual resolver
behavior (cache, one-step English fallback, locale switch/invalidation,
tombstone-id/oversize/invalid-id bounds safety) instead of only checking
generated text, mirroring the byte-exact host-native pattern already used
by scripts/modernize/tests/test_save_format_meta_bytes_native.py.

This module also proves -- by scanning the real source text -- that
src/expansion_locale.c and include/expansion_locale.h never reference any
vanilla language runtime symbol (GetLang/SetLang/gLanguageMode), any
vanilla message table (gMsgTable), or any XMAP identifier: the isolation
guarantee issue #18 sprint 1 requires.
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.catalog import DEFAULT_CATALOG_PATHS
from scripts.localization.generate import generate

DRIVER_C = Path(__file__).resolve().with_name("host_resolver_driver.c")

FORBIDDEN_VANILLA_TOKENS = (
    "GetLang",
    "SetLang",
    "gLanguageMode",
    "gMsgTable",
    "XMAP",
)


class ResolverNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = "cc"
        try:
            subprocess.run([cc, "--version"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, check=True)
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest("no host 'cc' compiler available")
        cls.cc = cc

    def _build_and_run(self, tmp_path, sparse_ja_title=False):
        generated_dir = tmp_path / "generated"
        catalog_paths = None
        if sparse_ja_title:
            ja_data = json.loads(
                DEFAULT_CATALOG_PATHS["ja"].read_text(encoding="utf-8")
            )
            del ja_data["strings"]["framework.title"]
            sparse_ja_path = tmp_path / "catalog.ja.json"
            sparse_ja_path.write_text(
                json.dumps(ja_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            catalog_paths = dict(DEFAULT_CATALOG_PATHS)
            catalog_paths["ja"] = sparse_ja_path
        generate(output_dir=generated_dir, catalog_paths=catalog_paths)
        binary = tmp_path / "host_resolver_driver"
        cmd = [
            self.cc, "-std=gnu89", "-Wall", "-Wextra",
            "-Werror=declaration-after-statement",
            "-I", str(ROOT / "include"),
            "-I", str(generated_dir),
            "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x87u",
            "-DFE8_EXPANSION_DEFAULT_LOCALE_ID=0u",
            "-DFE8_EXPANSION_PSEUDO_LOCALE_ENABLED=1",
        ]
        if sparse_ja_title:
            cmd.append("-DTEST_JA_TITLE_FALLS_BACK=1")
        cmd.extend(
            [
                str(DRIVER_C),
                str(ROOT / "src" / "expansion_locale.c"),
                str(generated_dir / "expansion_locale_catalog.c"),
                "-o", str(binary),
            ]
        )
        compile_result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        self.assertEqual(compile_result.returncode, 0, compile_result.stdout)
        run_result = subprocess.run(
            [str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        return run_result

    def test_resolver_smoke_checks_pass_natively(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_result = self._build_and_run(Path(tmp))
            self.assertEqual(run_result.returncode, 0, run_result.stdout)
            self.assertIn("ALL HOST SMOKE CHECKS PASSED", run_result.stdout)
            self.assertNotIn("FAIL:", run_result.stdout)

    def test_resolver_run_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            result_a = self._build_and_run(Path(tmp_a))
            result_b = self._build_and_run(Path(tmp_b))
            self.assertEqual(result_a.stdout, result_b.stdout)

    def test_missing_japanese_entry_falls_back_to_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_result = self._build_and_run(Path(tmp), sparse_ja_title=True)
            self.assertEqual(run_result.returncode, 0, run_result.stdout)
            self.assertIn("JA[0] = Expansion Framework", run_result.stdout)


class VanillaIsolationSourceAuditTests(unittest.TestCase):
    """Source-text audit: the new locale runtime must never reference any
    vanilla language-runtime/message-table/XMAP symbol."""

    @staticmethod
    def _strip_c_comments(text):
        """Removes /* ... */ and // ... comments so the audit only flags
        *code* references to a forbidden vanilla symbol -- explanatory
        prose in a comment about what this file deliberately does NOT
        touch is expected and fine."""
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
        text = re.sub(r"//[^\n]*", " ", text)
        return text

    def _assert_clean(self, path):
        text = self._strip_c_comments(path.read_text(encoding="utf-8"))
        for token in FORBIDDEN_VANILLA_TOKENS:
            self.assertNotIn(
                token, text,
                f"{path} unexpectedly references vanilla symbol {token!r} in code",
            )

    def test_expansion_locale_header_is_isolated(self):
        self._assert_clean(ROOT / "include" / "expansion_locale.h")

    def test_expansion_locale_source_is_isolated(self):
        self._assert_clean(ROOT / "src" / "expansion_locale.c")

    def test_generated_catalog_c_is_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_dir = Path(tmp) / "generated"
            generate(output_dir=generated_dir)
            self._assert_clean(generated_dir / "expansion_locale_catalog.c")
            self._assert_clean(generated_dir / "expansion_msg_ids.h")


if __name__ == "__main__":
    unittest.main()
