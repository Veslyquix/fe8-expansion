import hashlib
import json
import struct
import subprocess
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
    check_compact_assets,
)


class CjkFontTests(unittest.TestCase):
    SCRATCH = Path(__file__).resolve().parent / ".scratch"

    def test_expansion_catalog_inventory_provenance_matches_current_34_keys(self):
        inventory = json.loads((ROOT / "fonts/cjk/inventory.json").read_text())
        registry_path = ROOT / "texts/expansion/registry.json"
        registry = json.loads(registry_path.read_text())
        active_keys = {
            record["key"]
            for record in registry["messages"]
            if record["status"] == "active"
        }
        self.assertEqual(len(active_keys), 34)

        catalog_paths = sorted((ROOT / "texts/expansion").glob("catalog.*.json"))
        source_paths = [registry_path, *catalog_paths]
        for path in source_paths:
            relative_path = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            self.assertEqual(
                inventory["inputs"][relative_path],
                {
                    "byte_count": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                },
            )

        for path in catalog_paths:
            catalog = json.loads(path.read_text())
            self.assertEqual(set(catalog["strings"]), active_keys)

        expected_catalogs = [
            path.relative_to(ROOT).as_posix() for path in catalog_paths
        ]
        for locale in ("ja", "zh-Hans"):
            expansion = inventory["locales"][locale]["expansion"]
            self.assertEqual(
                expansion["active_key_count"],
                len(active_keys),
            )
            self.assertEqual(expansion["catalogs"], expected_catalogs)

    def test_inventory_counts_tokens_and_spacing_contract(self):
        inventory = json.loads((ROOT / "fonts/cjk/inventory.json").read_text())
        self.assertEqual(inventory["union"]["spacing_scalars"], ["U+3000"])
        locale_scalars = {}
        for locale in ("ja", "zh-Hans"):
            record = inventory["locales"][locale]
            expected_source_count = (
                record["glyph_scalar_count"]
                + len(record["spacing_scalars"])
                + len(record["nonrendering_scalars"])
            )
            self.assertEqual(
                record["source_non_ascii_scalar_count"],
                expected_source_count,
            )
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
                self.assertEqual(len(corpus), record["glyph_scalar_count"])
            locale_scalars[locale] = set(
                map(ord, (ROOT / f"fonts/cjk/corpora/{locale}.system.txt").read_text())
            )

        union = set(map(ord, (ROOT / "fonts/cjk/corpora/union.txt").read_text()))
        self.assertEqual(union, set().union(*locale_scalars.values()))
        self.assertEqual(len(union), inventory["union"]["glyph_scalar_count"])
        self.assertEqual(
            inventory["union"]["source_non_ascii_scalar_count"],
            inventory["union"]["glyph_scalar_count"]
            + len(inventory["union"]["spacing_scalars"]),
        )
        self.assertIn(0x5019, locale_scalars["ja"])
        self.assertIn(0x5019, locale_scalars["zh-Hans"])
        self.assertIn(0x8A3A, locale_scalars["ja"])
        self.assertIn(0x8BCA, locale_scalars["zh-Hans"])

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

    def test_compact_asset_validation_is_deterministic(self):
        first = check_compact_assets(ROOT)
        second = check_compact_assets(ROOT)
        self.assertEqual(first, second)

    def test_febuilder_gate_counts_follow_current_manifest(self):
        manifest = json.loads(
            (ROOT / "fonts/cjk/febuilder-manifest.json").read_text()
        )
        gates = json.loads(
            (ROOT / "fonts/cjk/reports/febuilder-gates.json").read_text()
        )
        expected_rows = sum(
            len((ROOT / "fonts/cjk" / job["corpus"]["path"]).read_text())
            for job in manifest["jobs"]
        )
        for gate in gates["gates"].values():
            self.assertEqual(gate["job_count"], len(manifest["jobs"]))
            self.assertEqual(gate["row_count"], expected_rows)

    def test_aggregate_maps_widths_and_bitmaps_are_valid(self):
        manifest = json.loads(
            (ROOT / "graphics/fonts/cjk/manifest.json").read_text()
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
        payload_total = 0
        aligned_total = 0
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
                payload_total += len(data)
                aligned_total += (len(data) + 3) & ~3
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    asset[kind]["sha256"],
                )
        self.assertEqual(manifest["rom_budget"]["payload_bytes"], payload_total)
        self.assertEqual(
            manifest["rom_budget"]["four_byte_aligned_blob_bytes"],
            aligned_total,
        )

    def test_font_domain_contains_no_committed_package_archive(self):
        tracked = subprocess.run(
            (
                "git",
                "ls-files",
                "-z",
                "--",
                "fonts/cjk",
                "graphics/fonts/cjk",
                "scripts/fonttools/cjk",
                "cjk_fonts.mk",
                "docs/cjk_fonts.md",
            ),
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode("utf-8")
        for relative_path in filter(None, tracked.split("\0")):
            path = ROOT / relative_path
            self.assertNotEqual(path.suffix.lower(), ".zip", path)
            with path.open("rb") as source:
                signature = source.read(4)
            self.assertNotIn(
                signature,
                (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
                path,
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
