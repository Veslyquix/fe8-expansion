import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "shiftcheck" / "tas"))

import retime_gbahawk_movie as retime


class RetimeGbahawkMovieTests(unittest.TestCase):
    def make_movie(self, root: Path) -> Path:
        movie = root / "input.gbmv"
        with zipfile.ZipFile(movie, "w") as output:
            output.writestr("Header.txt", "GameName fixture\nSHA1 OLD\n")
            output.writestr(
                "Input Log.txt",
                "[Input]\nLogKey:fixture\n|...........|\n|....S......|\n|.......A...|\n[/Input]\n",
            )
            output.writestr("SyncSettings.json", "{}")
        return movie

    def test_applies_sequential_operations_and_rewrites_rom_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            movie = self.make_movie(root)
            rom = root / "test.gba"
            rom.write_bytes(b"rom")
            patch = root / "patch.json"
            patch.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "operations": [
                            {"op": "move", "from": 1, "to": 0, "keys": ["START"]},
                            {"op": "insert", "frame": 1, "count": 1, "keys": ["B"]},
                            {"op": "add", "frame": 2, "keys": ["A"]},
                            {"op": "remove", "frame": 3, "keys": ["A"]},
                            {"op": "set", "frame": 3, "keys": ["UP", "L"]},
                            {"op": "delete", "frame": 1, "count": 1},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output.gbmv"

            retime.retime(movie, rom, patch, output)

            with zipfile.ZipFile(output) as result:
                header = result.read("Header.txt").decode()
                input_log = result.read("Input Log.txt").decode().splitlines()
            self.assertIn("SHA1 " + hashlib.sha1(b"rom").hexdigest().upper(), header)
            self.assertEqual(
                [line for line in input_log if line.startswith("|")],
                ["|....S......|", "|.......A...|", "|U.......l..|"],
            )

    def test_rejects_unknown_key(self):
        rows = [list("...........")]
        with self.assertRaisesRegex(retime.RetimeError, "must be one of"):
            retime.apply_patch(
                rows,
                {
                    "schema_version": 1,
                    "operations": [{"op": "add", "frame": 0, "keys": ["NOPE"]}],
                },
            )

    def test_rejects_delete_past_end(self):
        rows = [list("...........")]
        with self.assertRaisesRegex(retime.RetimeError, "deletes past movie length"):
            retime.apply_patch(
                rows,
                {
                    "schema_version": 1,
                    "operations": [{"op": "delete", "frame": 0, "count": 2}],
                },
            )


if __name__ == "__main__":
    unittest.main()
