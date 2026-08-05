"""Host-native strict-C89 test for the real localized text decoder."""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEST_DIR = Path(__file__).resolve().parent
BUILD_DIR = TEST_DIR / ".localized_text_codec_host_build"
sys.path.insert(0, str(ROOT / "scripts" / "texttools"))

from multilang_codec import build_catalog  # noqa: E402


CORPUS = (
    b"ASCII|"
    + "日本語|中文|😀|𠮷|".encode("utf-8")
    + bytes((0x80, 0x01, 0x10, 0x02, 0x03, 0x23, 0x7F, 0xE9))
    + b"|ODD\x00"
)


def _c_bytes(data: bytes) -> str:
    return ", ".join("0x{:02X}".format(value) for value in data)


def _write_fixture(path: Path) -> None:
    catalog = build_catalog((CORPUS,))
    entry = catalog.entries[0]
    if entry.pointer_offset is None or catalog.root_index is None:
        raise AssertionError("host fixture catalog is unexpectedly absent")
    compressed = catalog.compressed_blob[
        entry.pointer_offset:entry.pointer_offset + entry.compressed_size
    ]
    nodes = ", ".join("0x{:08X}u".format(node) for node in catalog.nodes)
    text = """\
#ifndef GUARD_LOCALIZED_TEXT_CODEC_HOST_FIXTURE_H
#define GUARD_LOCALIZED_TEXT_CODEC_HOST_FIXTURE_H

#define HOST_FIXTURE_ROOT_INDEX {root}u
#define HOST_FIXTURE_EXPECTED_SIZE {size}u

static const u32 gHostFixtureNodes[] = {{ {nodes} }};
static const u8 gHostFixtureCompressed[] = {{ {compressed} }};
static const u8 gHostFixtureExpected[] = {{ {expected} }};

#endif
""".format(
        root=catalog.root_index,
        size=len(CORPUS),
        nodes=nodes,
        compressed=_c_bytes(compressed),
        expected=_c_bytes(CORPUS),
    )
    path.write_text(text, encoding="ascii")


class LocalizedTextCodecNativeTests(unittest.TestCase):
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
            raise unittest.SkipTest("no host 'cc' compiler available")

    def test_real_c_decoder_compiles_c89_and_passes_driver(self):
        if BUILD_DIR.exists():
            shutil.rmtree(BUILD_DIR)
        BUILD_DIR.mkdir()
        try:
            fixture = BUILD_DIR / "localized_text_codec_host_fixture.h"
            binary = BUILD_DIR / "localized_text_codec_host_test"
            _write_fixture(fixture)

            compile_result = subprocess.run(
                [
                    "cc",
                    "-std=c89",
                    "-pedantic-errors",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-DMODERN=1",
                    "-I",
                    str(TEST_DIR / "host_include"),
                    "-I",
                    str(ROOT / "include"),
                    "-I",
                    str(BUILD_DIR),
                    str(ROOT / "src" / "localized_text_codec.c"),
                    str(TEST_DIR / "localized_text_codec_host_test.c"),
                    "-o",
                    str(binary),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(
                compile_result.returncode,
                0,
                "strict-C89 host compile failed:\n{}".format(compile_result.stdout),
            )

            run_result = subprocess.run(
                [str(binary)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(
                run_result.returncode,
                0,
                "host decoder driver failed:\n{}".format(run_result.stdout),
            )
            self.assertEqual(
                run_result.stdout.strip(),
                "localized_text_codec_host_test: ok",
            )
        finally:
            if BUILD_DIR.exists():
                shutil.rmtree(BUILD_DIR)


if __name__ == "__main__":
    unittest.main()
