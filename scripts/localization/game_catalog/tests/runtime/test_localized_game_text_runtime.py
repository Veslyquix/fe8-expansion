from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
TEST_DIR = Path(__file__).resolve().parent
HOST_INCLUDE = TEST_DIR / "host_include"
BUILD_ROOT = TEST_DIR / ".build"
sys.path.insert(0, str(ROOT))

from scripts.texttools.multilang_codec import build_catalog  # noqa: E402

RUNTIME_DRIVER = TEST_DIR / "runtime_driver.c"
ENGLISH_PROBE = TEST_DIR / "layout_english_probe.c"
CJK_FLOOR_PROBE = TEST_DIR / "layout_cjk_floor_probe.c"
CJK_GROWTH_PROBE = TEST_DIR / "layout_cjk_growth_probe.c"
FUNCTION_MACRO_PROBE = TEST_DIR / "function_macro_probe.c"
FALLBACK_CORPUS_DRIVER = TEST_DIR / "fallback_corpus_driver.c"

JA_MESSAGES = (
    "猫\x1f\x00".encode("utf-8"),
    None,
    (("語" * 8) + "\x1f\x00").encode("utf-8"),
    "壊\x1f\x00".encode("utf-8"),
    None,
    "\u3000\x1f\x00".encode("utf-8"),
    None,
    None,
    None,
    None,
    None,
    None,
    None,
)

ENGLISH_MESSAGES = (
    b"Cat\x1f\x00",
    b"Fallback\x1f\x00",
    b"Long English\x1f\x00",
    b"Broken\x1f\x00",
    b"Plain English\x1f\x00",
    b"Space\x1f\x00",
    b"Rennac, Rich \x93Merchant\x94\x1f\x00",
    b"A\x7fB\xe9C\x81\x40D\x1f\x00",
    b"\x10\x93\x94\x80\xe9X\x1f\x00",
    b"\x10\x93\x00",
    b"\x80\x00",
    b"\x82\x00",
    b"\x81\x41\x00",
)


def _c_bytes(data: bytes) -> str:
    return ", ".join("0x{:02X}".format(value) for value in data)


class LocalizedGameTextRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "size"):
            try:
                subprocess.run(
                    [tool, "--version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            except (OSError, subprocess.CalledProcessError):
                raise unittest.SkipTest(f"no host {tool!r} tool available")

    def setUp(self):
        if BUILD_ROOT.exists():
            shutil.rmtree(BUILD_ROOT)
        BUILD_ROOT.mkdir(parents=True)

    def tearDown(self):
        if BUILD_ROOT.exists():
            shutil.rmtree(BUILD_ROOT)

    def _run(self, cmd, cwd=ROOT):
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def _write_runtime_fixture(self, build_dir: Path):
        catalog = build_catalog(JA_MESSAGES)
        english_catalog = build_catalog(ENGLISH_MESSAGES)
        if catalog.root_index is None:
            raise AssertionError("fixture catalog unexpectedly missing root")
        if english_catalog.root_index is None:
            raise AssertionError("English fixture catalog unexpectedly missing root")

        max_decoded = max(len(msg) for msg in JA_MESSAGES if msg is not None)
        config_header = build_dir / "localized_game_text_data.h"
        catalog_header = build_dir / "game_localization_catalog.h"
        source = build_dir / "localized_game_text_fixture.c"

        entries = []
        for index, entry in enumerate(catalog.entries):
            if entry.pointer_offset is None:
                entries.append("    { 0, 0u, 0u, 0u, 0u, 0u, 1u, 0u },")
                continue

            bit_length = entry.bit_length
            if index == 3:
                bit_length -= 1
            entries.append(
                "    {{ gJaCompressed + {offset}u, {size}u, {bits}u, {decoded}u, "
                "1u, 1u, 0u, 0u }},".format(
                    offset=entry.pointer_offset,
                    size=entry.compressed_size,
                    bits=bit_length,
                    decoded=entry.decoded_size,
                )
            )

        nodes = ", ".join("0x{:08X}u".format(node) for node in catalog.nodes)
        config_header.write_text(
            "#ifndef GUARD_LOCALIZED_GAME_TEXT_DATA_H\n"
            "#define GUARD_LOCALIZED_GAME_TEXT_DATA_H\n\n"
            "#define FE8_GAME_LOCALIZATION_DATA_PRESENT 1\n"
            "#define FE8_GAME_LOCALIZATION_TARGET_COUNT {}u\n"
            "#define FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES {}u\n\n"
            "#endif\n".format(len(JA_MESSAGES), max_decoded),
            encoding="ascii",
        )
        catalog_header.write_text(
            "#ifndef GUARD_GAME_LOCALIZATION_CATALOG_H\n"
            "#define GUARD_GAME_LOCALIZATION_CATALOG_H\n\n"
            "#define GAME_LOCALIZATION_LOCALE_JA 0u\n"
            "#define GAME_LOCALIZATION_LOCALE_ZH_HANS 1u\n"
            "#define GAME_LOCALIZATION_LOCALE_COUNT 2u\n\n"
            "struct GameLocalizationCatalogEntry\n"
            "{\n"
            "    const u8 *data;\n"
            "    u32 compressedSize;\n"
            "    u32 bitLength;\n"
            "    u32 maxDecodedBytes;\n"
            "    u8 present;\n"
            "    u8 providerKind;\n"
            "    u8 fallbackKind;\n"
            "    u8 reserved;\n"
            "};\n\n"
            "struct GameLocalizationLocaleCatalog\n"
            "{\n"
            "    const u32 *nodes;\n"
            "    u32 nodeCount;\n"
            "    u32 rootIndex;\n"
            "    const u8 *compressedBlob;\n"
            "    u32 compressedSize;\n"
            "    const struct GameLocalizationCatalogEntry *entries;\n"
            "    u32 entryCount;\n"
            "    u32 maxDecodedBytes;\n"
            "    u32 presentCount;\n"
            "    u32 explicitFallbackCount;\n"
            "    u32 providerUnavailableCount;\n"
            "};\n\n"
            "extern const struct GameLocalizationLocaleCatalog *const\n"
            "    gGameLocalizationCatalogs[GAME_LOCALIZATION_LOCALE_COUNT];\n\n"
            "#endif\n",
            encoding="ascii",
        )
        english_nodes = ", ".join(
            "0x{:08X}u".format(node) for node in english_catalog.nodes
        )
        english_pointers = []
        for entry in english_catalog.entries:
            if entry.pointer_offset is None:
                raise AssertionError("English fixture unexpectedly has an absent entry")
            english_pointers.append(
                "    gEnglishCompressed + {}u,".format(entry.pointer_offset)
            )

        source_text = (
            "#include \"global.h\"\n"
            "#include \"localized_game_text.h\"\n"
            "#include \"game_localization_catalog.h\"\n\n"
            "const u32 gMsgHuffmanTable[] = {{{english_nodes}}};\n"
            "const u32 *const gMsgHuffmanTableRoot = "
            "gMsgHuffmanTable + {english_root}u;\n"
            "static const u8 gEnglishCompressed[] = {{{english_blob}}};\n"
            "const u8 *const gMsgTable[] = {{\n"
            "{english_pointers}\n"
            "}};\n\n"
            "static const u32 gJaNodes[] = {{{nodes}}};\n"
            "static const u8 gJaCompressed[] = {{{blob}}};\n"
            "static const struct GameLocalizationCatalogEntry gJaEntries[] = "
            "{{{entries_text}\n}};\n\n"
            "static const struct GameLocalizationLocaleCatalog gJaCatalog = {{\n"
            "    gJaNodes, {node_count}u, {root_index}u,\n"
            "    gJaCompressed, {compressed_size}u,\n"
            "    gJaEntries, {entry_count}u, {max_decoded}u,\n"
            "    {present_count}u, {fallback_count}u, 0u\n"
            "}};\n\n"
            "const struct GameLocalizationLocaleCatalog *const\n"
            "    gGameLocalizationCatalogs[GAME_LOCALIZATION_LOCALE_COUNT] = {{\n"
            "        &gJaCatalog,\n"
            "        0\n"
            "    }};\n"
        ).format(
            english_nodes=english_nodes,
            english_root=english_catalog.root_index,
            english_blob=_c_bytes(english_catalog.compressed_blob),
            english_pointers="\n".join(english_pointers),
            nodes=nodes,
            blob=_c_bytes(catalog.compressed_blob),
            entries_text="\n".join(entries),
            node_count=len(catalog.nodes),
            root_index=catalog.root_index,
            entry_count=len(JA_MESSAGES),
            compressed_size=len(catalog.compressed_blob),
            max_decoded=max_decoded,
            present_count=sum(message is not None for message in JA_MESSAGES),
            fallback_count=sum(message is None for message in JA_MESSAGES),
        )
        source.write_text(source_text, encoding="ascii")
        return config_header, source

    def _write_probe_header(
        self, build_dir: Path, max_decoded: int, target_count: int = 5
    ):
        header = build_dir / "localized_game_text_data.h"
        header.write_text(
            "#ifndef GUARD_LOCALIZED_GAME_TEXT_DATA_H\n"
            "#define GUARD_LOCALIZED_GAME_TEXT_DATA_H\n\n"
            "#define FE8_GAME_LOCALIZATION_DATA_PRESENT 1\n"
            "#define FE8_GAME_LOCALIZATION_TARGET_COUNT {}u\n"
            "#define FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES {}u\n\n"
            "#endif\n".format(target_count, max_decoded),
            encoding="ascii",
        )
        return header

    def test_runtime_driver(self):
        build_dir = BUILD_ROOT / "runtime"
        build_dir.mkdir()
        _, fixture_c = self._write_runtime_fixture(build_dir)
        binary = build_dir / "runtime_driver"

        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Werror=declaration-after-statement",
                "-fcf-protection=none",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x07u",
                "-I",
                str(HOST_INCLUDE),
                "-I",
                str(ROOT / "include"),
                "-I",
                str(build_dir),
                str(ROOT / "src" / "localized_text_codec.c"),
                str(ROOT / "src" / "localized_game_text.c"),
                str(ROOT / "src" / "msg.c"),
                str(fixture_c),
                str(RUNTIME_DRIVER),
                "-o",
                str(binary),
            ]
        )
        run_result = self._run([str(binary)])
        self.assertEqual(run_result.stdout.strip(), "localized_game_text_runtime_driver: ok")

    def test_committed_fallback_corpus_through_c_runtime(self):
        build_dir = BUILD_ROOT / "fallback-corpus"
        build_dir.mkdir()
        self._write_probe_header(build_dir, 0x14D0, target_count=3414)
        mapping = json.loads(
            (ROOT / "texts" / "locales" / "mapping" / "fe8u_target_map.json").read_text(
                encoding="utf-8"
            )
        )
        fallback_ids = [
            int(row["target_id"], 16)
            for row in mapping["rows"]
            if row["source"]["kind"] == "english_fallback"
        ]
        self.assertEqual(len(fallback_ids), 1828)
        (build_dir / "fallback_corpus_ids.h").write_text(
            "static const int sFallbackIds[] = {\n"
            + "".join(
                "    0x{:03X},\n".format(msg_id) for msg_id in fallback_ids
            )
            + "};\n",
            encoding="ascii",
        )
        binary = build_dir / "fallback_corpus_driver"

        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Werror=declaration-after-statement",
                "-fcf-protection=none",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x07u",
                "-I",
                str(HOST_INCLUDE),
                "-I",
                str(ROOT / "include"),
                "-I",
                str(build_dir),
                str(ROOT / "src" / "msg.c"),
                str(ROOT / "src" / "msg_data.c"),
                str(FALLBACK_CORPUS_DRIVER),
                "-o",
                str(binary),
            ]
        )
        run_result = self._run([str(binary)])
        self.assertEqual(
            run_result.stdout.strip(),
            "fallback_corpus_driver: 1828 renderer-valid streams",
        )

    def test_profile_compiles_and_layout_probes(self):
        english_dir = BUILD_ROOT / "english"
        english_dir.mkdir()
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Werror=declaration-after-statement",
                "-fcf-protection=none",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x1u",
                "-I",
                str(HOST_INCLUDE),
                "-I",
                str(ROOT / "include"),
                "-c",
                str(ROOT / "src" / "msg.c"),
                "-o",
                str(english_dir / "msg.o"),
            ]
        )
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Werror=declaration-after-statement",
                "-fcf-protection=none",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x1u",
                "-I",
                str(HOST_INCLUDE),
                "-I",
                str(ROOT / "include"),
                "-c",
                str(ROOT / "src" / "localized_game_text.c"),
                "-o",
                str(english_dir / "localized_game_text.o"),
            ]
        )
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Werror=declaration-after-statement",
                "-fcf-protection=none",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x1u",
                "-I",
                str(HOST_INCLUDE),
                "-I",
                str(ROOT / "include"),
                "-c",
                str(ROOT / "src" / "localized_text_codec.c"),
                "-o",
                str(english_dir / "localized_text_codec.o"),
            ]
        )
        for object_name in ("localized_game_text.o", "localized_text_codec.o"):
            size_result = self._run(["size", "-A", str(english_dir / object_name)])
            alloc_lines = [
                line
                for line in size_result.stdout.splitlines()
                if line.strip().startswith((".text", ".data", ".bss", ".rodata"))
            ]
            self.assertTrue(
                all(int(line.split()[1]) == 0 for line in alloc_lines),
                size_result.stdout,
            )
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x1u",
                "-I",
                str(ROOT / "include"),
                "-c",
                str(ENGLISH_PROBE),
                "-o",
                str(english_dir / "layout_english_probe.o"),
            ]
        )

        legacy_dir = BUILD_ROOT / "legacy"
        legacy_dir.mkdir()
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Werror=declaration-after-statement",
                "-fcf-protection=none",
                "-I",
                str(HOST_INCLUDE),
                "-I",
                str(ROOT / "include"),
                "-c",
                str(ROOT / "src" / "msg.c"),
                "-o",
                str(legacy_dir / "msg.o"),
            ]
        )
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Werror=declaration-after-statement",
                "-fcf-protection=none",
                "-I",
                str(HOST_INCLUDE),
                "-I",
                str(ROOT / "include"),
                "-c",
                str(ROOT / "src" / "localized_game_text.c"),
                "-o",
                str(legacy_dir / "localized_game_text.o"),
            ]
        )
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(ROOT / "include"),
                "-c",
                str(ENGLISH_PROBE),
                "-o",
                str(legacy_dir / "layout_english_probe.o"),
            ]
        )

        floor_dir = BUILD_ROOT / "cjk-floor"
        floor_dir.mkdir()
        self._write_probe_header(floor_dir, 0x10)
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x07u",
                "-I",
                str(floor_dir),
                "-I",
                str(ROOT / "include"),
                "-c",
                str(CJK_FLOOR_PROBE),
                "-o",
                str(floor_dir / "layout_cjk_floor_probe.o"),
            ]
        )
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x07u",
                "-I",
                str(floor_dir),
                "-I",
                str(ROOT / "include"),
                "-c",
                str(FUNCTION_MACRO_PROBE),
                "-o",
                str(floor_dir / "function_macro_probe.o"),
            ]
        )

        growth_dir = BUILD_ROOT / "cjk-growth"
        growth_dir.mkdir()
        self._write_probe_header(growth_dir, 0x1601)
        self._run(
            [
                "cc",
                "-std=gnu89",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DMODERN=1",
                "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x07u",
                "-I",
                str(growth_dir),
                "-I",
                str(ROOT / "include"),
                "-c",
                str(CJK_GROWTH_PROBE),
                "-o",
                str(growth_dir / "layout_cjk_growth_probe.o"),
            ]
        )


if __name__ == "__main__":
    unittest.main()
