import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization import schema
from scripts.localization.catalog import load_catalog, parse_registry
from scripts.localization.schema import SchemaError


def _base_registry():
    return {
        "messages": [
            {
                "id": 0,
                "key": "a.one",
                "status": "active",
                "surface": "framework_generic",
                "max_width": 20,
                "max_decoded_bytes": 32,
            },
            {
                "id": 1,
                "key": "a.two",
                "status": "active",
                "surface": "framework_generic",
                "max_width": 20,
                "max_decoded_bytes": 32,
            },
        ]
    }


def _write(directory: Path, registry: dict, strings: dict):
    reg_path = directory / "registry.json"
    cat_path = directory / "catalog.en.json"
    reg_path.write_text(json.dumps(registry), encoding="utf-8")
    cat_path.write_text(json.dumps({"locale": "en", "strings": strings}), encoding="utf-8")
    return reg_path, cat_path


class ParseRegistryTests(unittest.TestCase):
    def test_valid_registry_parses(self):
        entries = parse_registry(_base_registry())
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].key, "a.one")

    def test_duplicate_id_rejected(self):
        reg = _base_registry()
        reg["messages"][1]["id"] = 0
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_duplicate_key_rejected(self):
        reg = _base_registry()
        reg["messages"][1]["key"] = "a.one"
        reg["messages"][1]["id"] = 5
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_out_of_order_ids_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["id"] = 5
        reg["messages"][1]["id"] = 1
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_negative_id_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["id"] = -1
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_max_assignable_id_65534_active_accepted(self):
        reg = _base_registry()
        reg["messages"][0]["id"] = 0
        reg["messages"][1]["id"] = schema.MSG_ID_MAX
        entries = parse_registry(reg)
        self.assertEqual(entries[1].id, 0xFFFE)

    def test_max_assignable_id_65534_tombstone_accepted(self):
        reg = _base_registry()
        reg["messages"].append(
            {"id": schema.MSG_ID_MAX, "key": "a.retired", "status": "tombstone"}
        )
        entries = parse_registry(reg)
        self.assertEqual(entries[2].id, 0xFFFE)
        self.assertEqual(entries[2].status, "tombstone")

    def test_sentinel_id_65535_active_rejected(self):
        reg = _base_registry()
        reg["messages"][1]["id"] = 0xFFFF
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_sentinel_id_65535_tombstone_rejected(self):
        reg = _base_registry()
        reg["messages"].append({"id": 0xFFFF, "key": "a.retired", "status": "tombstone"})
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_id_65536_rejected(self):
        reg = _base_registry()
        reg["messages"][1]["id"] = 65536
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_id_70000_rejected(self):
        reg = _base_registry()
        reg["messages"][1]["id"] = 70000
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_bool_id_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["id"] = True
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_float_id_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["id"] = 1.5
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_string_id_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["id"] = "0"
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_invalid_status_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["status"] = "bogus"
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_invalid_surface_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["surface"] = "not-a-surface"
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_max_width_out_of_range_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["max_width"] = 0
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_max_decoded_bytes_out_of_range_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["max_decoded_bytes"] = 0
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_tombstone_entry_needs_no_surface(self):
        reg = _base_registry()
        reg["messages"].append({"id": 2, "key": "a.retired", "status": "tombstone"})
        entries = parse_registry(reg)
        self.assertEqual(entries[2].status, "tombstone")
        self.assertIsNone(entries[2].surface)

    def test_reused_tombstone_id_rejected(self):
        # A tombstone entry occupies its id permanently; a later entry
        # (active or tombstone) must not reuse that same numeric id.
        reg = _base_registry()
        reg["messages"].append({"id": 2, "key": "a.retired", "status": "tombstone"})
        reg["messages"].append({"id": 2, "key": "a.reused", "status": "active",
                                 "surface": "framework_generic", "max_width": 10,
                                 "max_decoded_bytes": 16})
        with self.assertRaises(SchemaError):
            parse_registry(reg)

    def test_empty_messages_rejected(self):
        with self.assertRaises(SchemaError):
            parse_registry({"messages": []})


class LoadCatalogTests(unittest.TestCase):
    def test_valid_catalog_loads_with_pseudo_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path, cat_path = _write(
                tmp_path, _base_registry(), {"a.one": "Hello", "a.two": "World"}
            )
            loaded = load_catalog(registry_path=reg_path, catalog_en_path=cat_path)
            self.assertEqual(loaded.en_strings["a.one"], "Hello")
            self.assertIn("a.one", loaded.pseudo_strings)
            self.assertNotEqual(loaded.pseudo_strings["a.one"], loaded.en_strings["a.one"])

    def test_missing_catalog_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path, cat_path = _write(tmp_path, _base_registry(), {"a.one": "Hello"})
            with self.assertRaises(SchemaError):
                load_catalog(registry_path=reg_path, catalog_en_path=cat_path)

    def test_extra_catalog_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path, cat_path = _write(
                tmp_path, _base_registry(),
                {"a.one": "Hello", "a.two": "World", "a.extra": "Nope"},
            )
            with self.assertRaises(SchemaError):
                load_catalog(registry_path=reg_path, catalog_en_path=cat_path)

    def test_non_ascii_text_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path, cat_path = _write(
                tmp_path, _base_registry(), {"a.one": "Hell\u00f6", "a.two": "World"}
            )
            with self.assertRaises(SchemaError):
                load_catalog(registry_path=reg_path, catalog_en_path=cat_path)

    def test_width_overflow_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["max_width"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path, cat_path = _write(tmp_path, reg, {"a.one": "Hello", "a.two": "World"})
            with self.assertRaises(SchemaError):
                load_catalog(registry_path=reg_path, catalog_en_path=cat_path)

    def test_decoded_bytes_overflow_rejected(self):
        reg = _base_registry()
        reg["messages"][0]["max_decoded_bytes"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path, cat_path = _write(tmp_path, reg, {"a.one": "Hello", "a.two": "World"})
            with self.assertRaises(SchemaError):
                load_catalog(registry_path=reg_path, catalog_en_path=cat_path)

    def test_pseudo_overflow_rejected_even_if_english_fits(self):
        # English text fits its byte budget, but the pseudo transform's
        # deterministic vowel-doubling/bracket expansion pushes it over --
        # this must also fail visibly at build time (never silently pass).
        reg = _base_registry()
        reg["messages"][0]["max_decoded_bytes"] = 12
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path, cat_path = _write(
                tmp_path, reg, {"a.one": "aeiouaeiou", "a.two": "World"}
            )
            with self.assertRaises(SchemaError):
                load_catalog(registry_path=reg_path, catalog_en_path=cat_path)

    def test_placeholder_parity_holds_for_real_pseudo_transform(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path, cat_path = _write(
                tmp_path, _base_registry(), {"a.one": "Sample {0}", "a.two": "World"}
            )
            loaded = load_catalog(registry_path=reg_path, catalog_en_path=cat_path)
            self.assertIn("{0}", loaded.pseudo_strings["a.one"])

    def test_real_repository_registry_and_catalog_load_cleanly(self):
        # The committed texts/expansion/registry.json + catalog.en.json
        # this sprint ships must themselves pass every check above.
        loaded = load_catalog()
        self.assertGreater(len(loaded.active_entries), 0)
        self.assertGreaterEqual(len(loaded.tombstone_entries), 1)


if __name__ == "__main__":
    unittest.main()
