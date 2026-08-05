import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from scripts.fonttools.cjk.inventory import (
    FONT_SOURCES,
    build_generated_files,
    read_sfnt_identity,
)
from scripts.fonttools.cjk.package import (
    archive_package,
    build_compact_assets,
)


class CjkFontTests(unittest.TestCase):
    SCRATCH = Path(__file__).resolve().parent / ".scratch"

    def test_inventory_counts_tokens_and_spacing_contract(self):
        inventory = json.loads((ROOT / "fonts/cjk/inventory.json").read_text())
        self.assertEqual(
            (
                inventory["locales"]["ja"]["source_non_ascii_scalar_count"],
                inventory["locales"]["ja"]["glyph_scalar_count"],
            ),
            (1847, 1846),
        )
        self.assertEqual(
            (
                inventory["locales"]["zh-Hans"]["source_non_ascii_scalar_count"],
                inventory["locales"]["zh-Hans"]["glyph_scalar_count"],
            ),
            (2459, 2459),
        )
        self.assertEqual(
            (
                inventory["union"]["source_non_ascii_scalar_count"],
                inventory["union"]["glyph_scalar_count"],
            ),
            (3330, 3329),
        )
        self.assertEqual(inventory["union"]["spacing_scalars"], ["U+3000"])
        for locale in ("ja", "zh-Hans"):
            for style in ("system", "talk"):
                corpus = (
                    ROOT / f"fonts/cjk/corpora/{locale}.{style}.txt"
                ).read_text()
                self.assertTrue(corpus)
                self.assertFalse(any(character.isspace() for character in corpus))
                self.assertEqual(
                    tuple(map(ord, corpus)),
                    tuple(sorted(set(map(ord, corpus)))),
                )
                self.assertNotIn("[CTRL:", corpus)

    def test_inventory_regeneration_is_byte_identical(self):
        generated = build_generated_files(ROOT)
        for relative_path, expected in generated.items():
            self.assertEqual(
                (ROOT / relative_path).read_bytes(),
                expected,
                relative_path,
            )

    def test_font_identity_license_and_hash_pins(self):
        sources = json.loads((ROOT / "fonts/cjk/font-sources.json").read_text())
        self.assertEqual(sources["license"]["license_id"], "OFL-1.1")
        for locale, expected in FONT_SOURCES.items():
            path = ROOT / expected["path"]
            data = path.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected["sha256"])
            self.assertEqual(len(data), expected["byte_length"])
            identity = read_sfnt_identity(data)
            self.assertEqual(identity["family"], expected["family"])
            self.assertEqual(identity["version"], expected["version"])
            self.assertIn("Open Font License", identity["license"])
            self.assertEqual(
                sources["fonts"][locale]["source_url"],
                expected["source_url"],
            )

    def test_package_import_is_deterministic_and_matches_committed_assets(self):
        package = ROOT / "fonts/cjk/packages/febuilder-schema-v1.zip"
        report = ROOT / "fonts/cjk/reports/febuilder-generation-report.json"
        first = build_compact_assets(ROOT, package, report)
        second = build_compact_assets(ROOT, package, report)
        self.assertEqual(first, second)
        for relative_path, expected in first.items():
            self.assertEqual(
                (ROOT / relative_path).read_bytes(),
                expected,
                relative_path,
            )

    def test_aggregate_maps_widths_and_bitmaps_are_valid(self):
        manifest = json.loads(
            (ROOT / "graphics/fonts/cjk/manifest.json").read_text()
        )
        self.assertEqual(manifest["rom_budget"]["payload_bytes"], 594090)
        self.assertEqual(
            manifest["rom_budget"]["four_byte_aligned_blob_bytes"],
            594096,
        )
        self.assertEqual(
            manifest["spacing_scalars"],
            [
                {
                    "advance": 16,
                    "bitmap": None,
                    "locales": ["ja"],
                    "runtime_styles": ["system", "talk"],
                    "scalar": "U+3000",
                }
            ],
        )
        for name, asset in manifest["assets"].items():
            count = asset["glyph_count"]
            codepoints = (ROOT / asset["codepoints"]["path"]).read_bytes()
            widths = (ROOT / asset["widths"]["path"]).read_bytes()
            glyphs = (ROOT / asset["bitmap"]["path"]).read_bytes()
            values = struct.unpack(f"<{count}I", codepoints)
            self.assertEqual(values, tuple(sorted(set(values))), name)
            self.assertEqual(len(widths), count)
            self.assertTrue(all(1 <= width <= 16 for width in widths), name)
            self.assertEqual(len(glyphs), count * 64)
            self.assertTrue(
                all(any(glyphs[index : index + 64]) for index in range(0, len(glyphs), 64)),
                name,
            )
            for kind in ("codepoints", "widths", "bitmap"):
                data = (ROOT / asset[kind]["path"]).read_bytes()
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    asset[kind]["sha256"],
                )

    def test_package_zip_writer_is_byte_deterministic(self):
        self.SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".archive_",
            dir=self.SCRATCH,
        ) as temporary:
            base = Path(temporary)
            package = base / "package"
            package.mkdir()
            (package / "b.bin").write_bytes(b"b")
            (package / "a.bin").write_bytes(b"a")
            first = archive_package(package, base / "first.zip")
            second = archive_package(package, base / "second.zip")
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
