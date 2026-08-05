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
#define HOST_FIXTURE_BIT_LENGTH {bit_length}u

static const u32 gHostFixtureNodes[] = {{ {nodes} }};
static const u8 gHostFixtureCompressed[] = {{ {compressed} }};
static const u8 gHostFixtureExpected[] = {{ {expected} }};

#endif
""".format(
        root=catalog.root_index,
        size=len(CORPUS),
        bit_length=entry.bit_length,
        nodes=nodes,
        compressed=_c_bytes(compressed),
        expected=_c_bytes(CORPUS),
    )
    path.write_text(text, encoding="ascii")


class LocalizedTextCodecNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "nm", "size"):
            try:
                subprocess.run(
                    [tool, "--version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            except (OSError, subprocess.CalledProcessError):
                raise unittest.SkipTest("no host {!r} tool available".format(tool))

    def setUp(self):
        if BUILD_DIR.exists():
            shutil.rmtree(BUILD_DIR)
        BUILD_DIR.mkdir()

    def tearDown(self):
        if BUILD_DIR.exists():
            shutil.rmtree(BUILD_DIR)

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
            ]
            + arguments,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            "strict-C89 host compile failed:\n{}".format(result.stdout),
        )

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

    def test_disabled_profiles_emit_no_declarations_or_payload(self):
        probe = BUILD_DIR / "disabled_header_probe.c"
        probe.write_text(
            """\
#include "global.h"
#include "localized_text_codec.h"

enum LocalizedTextCodecStatus
{
    LOCALIZED_TEXT_CODEC_DISABLED_SENTINEL = 0
};

int LocalizedTextCodec_Decode(void)
{
    return LOCALIZED_TEXT_CODEC_DISABLED_SENTINEL;
}
""",
            encoding="ascii",
        )

        profiles = (
            ("non-modern", []),
            (
                "modern-english",
                ["-DMODERN=1", "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x1u"],
            ),
        )
        for name, defines in profiles:
            with self.subTest(profile=name):
                object_path = BUILD_DIR / "{}.o".format(name)
                probe_path = BUILD_DIR / "{}-probe.o".format(name)
                include_flags = [
                    "-I",
                    str(TEST_DIR / "host_include"),
                    "-I",
                    str(ROOT / "include"),
                ]
                self._compile(
                    defines
                    + include_flags
                    + [
                        "-c",
                        str(ROOT / "src" / "localized_text_codec.c"),
                        "-o",
                        str(object_path),
                    ]
                )
                self._compile(
                    defines
                    + include_flags
                    + ["-c", str(probe), "-o", str(probe_path)]
                )
                self._assert_zero_object(object_path)

    def test_real_c_decoder_compiles_c89_and_passes_driver(self):
        fixture = BUILD_DIR / "localized_text_codec_host_fixture.h"
        binary = BUILD_DIR / "localized_text_codec_host_test"
        _write_fixture(fixture)

        self._compile(
            [
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x7u",
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
        self.assertEqual(
            run_result.returncode,
            0,
            "host decoder driver failed:\n{}".format(run_result.stdout),
        )
        self.assertEqual(
            run_result.stdout.strip(),
            "localized_text_codec_host_test: ok",
        )


if __name__ == "__main__":
    unittest.main()
