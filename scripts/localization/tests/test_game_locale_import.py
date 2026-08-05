import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_locales.importer import (
    CN_SOURCE_ID,
    JP_CONTROLS_SOURCE_ID,
    JP_SOURCE_ID,
    MAPPING_SOURCE_ID,
    PINNED_SOURCE_SHA256,
    import_locale_sources,
    sha256_bytes,
    verify_source_hash,
)
from scripts.localization.game_locales.parsers import (
    LocaleSourceError,
    parse_hash_indexed,
)


class GameLocaleImportTests(unittest.TestCase):
    MANIFEST_PATH = ROOT / "texts/locales/manifest.json"

    def test_manifest_pins_exact_input_hashes_and_counts(self):
        manifest = json.loads(self.MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            {key: value["sha256"] for key, value in manifest["inputs"].items()},
            PINNED_SOURCE_SHA256,
        )
        self.assertEqual(manifest["locales"]["ja"]["indexed"]["message_count"], 3339)
        self.assertEqual(
            manifest["locales"]["zh-Hans"]["indexed"]["message_count"],
            3339,
        )
        self.assertEqual(manifest["locales"]["zh-Hans"]["raw"]["record_count"], 152)
        self.assertEqual(
            manifest["locales"]["zh-Hans"]["raw"]["unique_address_count"],
            143,
        )
        self.assertEqual(manifest["source_layout"]["fe8u_target_count"], 3414)
        self.assertEqual(
            manifest["mapping_seed"]["provenance_tag_counts"],
            {
                "auto:same": 1,
                "auto:shifted": 338,
                "extrap": 98,
                "interp": 2325,
                "seed:bmreliance-affinity": 8,
            },
        )

    def test_manifest_artifact_hashes_match_committed_bytes(self):
        manifest = json.loads(self.MANIFEST_PATH.read_text(encoding="utf-8"))
        for relative_path, expected in manifest["artifacts"].items():
            content = (ROOT / "texts/locales" / relative_path).read_bytes()
            self.assertEqual(sha256_bytes(content), expected["sha256"])
            self.assertEqual(len(content), expected["byte_count"])

    def test_manifest_payload_statistics_match_committed_sources(self):
        manifest = json.loads(self.MANIFEST_PATH.read_text(encoding="utf-8"))
        for locale in ("ja", "zh-Hans"):
            messages = parse_hash_indexed(
                (ROOT / f"texts/locales/{locale}/indexed.txt").read_text(
                    encoding="utf-8"
                )
            )
            stats = manifest["locales"][locale]["indexed"]
            self.assertEqual(
                sum(len(message.text) for message in messages),
                stats["payload_codepoint_count"],
            )
            self.assertEqual(
                len(set("".join(message.text for message in messages))),
                stats["unique_payload_codepoint_count"],
            )
            self.assertEqual(
                max(len(message.text.encode("utf-8")) for message in messages),
                stats["max_utf8_payload_bytes"],
            )

    def test_source_hash_verification_rejects_modified_bytes(self):
        test_dir = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(
            prefix=".game_locale_hash_",
            dir=test_dir,
        ) as temporary:
            path = Path(temporary) / "source.txt"
            path.write_text("source\n", encoding="utf-8")
            correct = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(
                verify_source_hash(path, "fixture", correct),
                b"source\n",
            )
            path.write_text("modified\n", encoding="utf-8")
            with self.assertRaisesRegex(LocaleSourceError, "SHA-256 mismatch"):
                verify_source_hash(path, "fixture", correct)

    def _reconstruct_inputs(self, directory: Path):
        japanese_path = directory / "jp.txt"
        controls_path = directory / "controls.txt"
        chinese_path = directory / "cn.txt"
        mapping_path = directory / "mapping.tsv"

        shutil.copyfile(ROOT / "texts/locales/ja/indexed.txt", japanese_path)
        shutil.copyfile(ROOT / "texts/locales/ja/control_defs.txt", controls_path)

        chinese_messages = parse_hash_indexed(
            (ROOT / "texts/locales/zh-Hans/indexed.txt").read_text(encoding="utf-8")
        )
        raw = json.loads(
            (ROOT / "texts/locales/zh-Hans/raw.json").read_text(encoding="utf-8")
        )
        cn_lines = []
        for message in chinese_messages:
            width = 2 if message.id < 0x100 else 4
            cn_lines.append(f"[{message.id:0{width}X}]")
            cn_lines.extend(message.text.split("\n"))
        raw_occurrences = []
        for record in raw["records"]:
            for provenance in record["provenance"]:
                raw_occurrences.append(
                    (provenance["record_index"], record["address"][2:], record["text"])
                )
        for _, address, text in sorted(raw_occurrences):
            cn_lines.append(f"[{address}]")
            cn_lines.extend(text.split("\n"))
        chinese_path.write_text("\n".join(cn_lines) + "\n", encoding="utf-8")

        candidate = json.loads(
            (
                ROOT / "texts/locales/mapping/fe8j_to_fe8u.candidates.json"
            ).read_text(encoding="utf-8")
        )
        mapping_lines = ["# us_id\tjp_id\tsource"]
        for row in candidate["rows"]:
            mapping_lines.append(
                "\t".join(
                    (
                        row["target_id"][2:],
                        row["source"]["id"][2:],
                        row["candidate_provenance"]["seed_tag"],
                    )
                )
            )
        mapping_path.write_text("\n".join(mapping_lines) + "\n", encoding="ascii")

        paths = {
            JP_SOURCE_ID: japanese_path,
            JP_CONTROLS_SOURCE_ID: controls_path,
            CN_SOURCE_ID: chinese_path,
            MAPPING_SOURCE_ID: mapping_path,
        }
        hashes = {
            source_id: hashlib.sha256(path.read_bytes()).hexdigest()
            for source_id, path in paths.items()
        }
        return paths, hashes

    def test_two_import_runs_are_byte_identical(self):
        test_dir = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(
            prefix=".game_locale_import_",
            dir=test_dir,
        ) as temporary:
            base = Path(temporary)
            inputs = base / "inputs"
            inputs.mkdir()
            paths, hashes = self._reconstruct_inputs(inputs)
            output_a = base / "a"
            output_b = base / "b"
            written_a = import_locale_sources(
                jp_text_path=paths[JP_SOURCE_ID],
                jp_controls_path=paths[JP_CONTROLS_SOURCE_ID],
                cn_text_path=paths[CN_SOURCE_ID],
                mapping_seed_path=paths[MAPPING_SOURCE_ID],
                output_dir=output_a,
                expected_hashes=hashes,
            )
            written_b = import_locale_sources(
                jp_text_path=paths[JP_SOURCE_ID],
                jp_controls_path=paths[JP_CONTROLS_SOURCE_ID],
                cn_text_path=paths[CN_SOURCE_ID],
                mapping_seed_path=paths[MAPPING_SOURCE_ID],
                output_dir=output_b,
                expected_hashes=hashes,
            )
            self.assertEqual(set(written_a), set(written_b))
            for relative_path in written_a:
                self.assertEqual(
                    written_a[relative_path].read_bytes(),
                    written_b[relative_path].read_bytes(),
                    relative_path,
                )


if __name__ == "__main__":
    unittest.main()
