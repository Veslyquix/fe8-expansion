import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_locales.controls import validate_canonical_text
from scripts.localization.game_locales.importer import (
    PINNED_SOURCE_SHA256,
    check_vendored_locale_sources,
    regenerate_vendored_locale_sources,
    sha256_bytes,
    vendored_source_paths,
    verify_source_hash,
)
from scripts.localization.game_locales.parsers import (
    LocaleSourceError,
    parse_hash_indexed,
)


class GameLocaleImportTests(unittest.TestCase):
    LOCALE_ROOT = ROOT / "texts/locales"
    SOURCE_ROOT = LOCALE_ROOT / "source"
    MANIFEST_PATH = LOCALE_ROOT / "manifest.json"

    def test_manifest_pins_exact_raw_snapshot_hashes_and_counts(self):
        manifest = json.loads(self.MANIFEST_PATH.read_text(encoding="utf-8"))
        paths = vendored_source_paths(self.SOURCE_ROOT)
        self.assertEqual(
            {source_id: sha256_bytes(path.read_bytes()) for source_id, path in paths.items()},
            PINNED_SOURCE_SHA256,
        )
        self.assertEqual(
            {key: value["sha256"] for key, value in manifest["inputs"].items()},
            PINNED_SOURCE_SHA256,
        )
        self.assertEqual(manifest["control_grammar"]["canonical_token"], "[CTRL:HHHH]")
        self.assertEqual(manifest["control_grammar"]["source_alias_count"], 34)
        self.assertEqual(manifest["control_grammar"]["fe8cn_additional_alias_count"], 20)
        self.assertEqual(manifest["locales"]["ja"]["indexed"]["message_count"], 3339)
        self.assertEqual(
            manifest["locales"]["zh-Hans"]["indexed"]["message_count"],
            3339,
        )
        self.assertEqual(manifest["locales"]["zh-Hans"]["raw"]["record_count"], 152)
        self.assertEqual(
            manifest["locales"]["zh-Hans"]["raw"]["unique_import_count"],
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
            content = (self.LOCALE_ROOT / relative_path).read_bytes()
            self.assertEqual(sha256_bytes(content), expected["sha256"])
            self.assertEqual(len(content), expected["byte_count"])

    def test_manifest_payload_statistics_match_canonical_sources(self):
        manifest = json.loads(self.MANIFEST_PATH.read_text(encoding="utf-8"))
        for locale in ("ja", "zh-Hans"):
            messages = parse_hash_indexed(
                (self.LOCALE_ROOT / locale / "indexed.txt").read_text(encoding="utf-8")
            )
            for message in messages:
                validate_canonical_text(message.text)
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

    def test_committed_raw_snapshots_regenerate_artifacts_byte_identically(self):
        checked = check_vendored_locale_sources(
            source_dir=self.SOURCE_ROOT,
            output_dir=self.LOCALE_ROOT,
        )
        self.assertIn("manifest.json", checked)

    def test_artifact_and_manifest_cannot_drift_together(self):
        test_dir = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(
            prefix=".game_locale_drift_",
            dir=test_dir,
        ) as temporary:
            output_dir = Path(temporary) / "out"
            regenerate_vendored_locale_sources(
                source_dir=self.SOURCE_ROOT,
                output_dir=output_dir,
            )
            artifact_path = output_dir / "ja/indexed.txt"
            artifact_path.write_bytes(artifact_path.read_bytes() + b"# drift\n")
            manifest_path = output_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact = artifact_path.read_bytes()
            manifest["artifacts"]["ja/indexed.txt"] = {
                "sha256": sha256_bytes(artifact),
                "byte_count": len(artifact),
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                LocaleSourceError,
                "do not match vendored raw snapshots",
            ):
                check_vendored_locale_sources(
                    source_dir=self.SOURCE_ROOT,
                    output_dir=output_dir,
                )

    def test_two_raw_snapshot_regenerations_are_byte_identical(self):
        test_dir = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(
            prefix=".game_locale_import_",
            dir=test_dir,
        ) as temporary:
            base = Path(temporary)
            written_a = regenerate_vendored_locale_sources(
                source_dir=self.SOURCE_ROOT,
                output_dir=base / "a",
            )
            written_b = regenerate_vendored_locale_sources(
                source_dir=self.SOURCE_ROOT,
                output_dir=base / "b",
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
