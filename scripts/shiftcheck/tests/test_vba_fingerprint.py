import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COLLECTOR = load_module(
    "collect_vba_fingerprint",
    ROOT / "scripts/shiftcheck/tas/collect_vba_fingerprint.py",
)
COMPARE = load_module("compare_vba", ROOT / "scripts/shiftcheck/tas/compare_vba.py")
PREPARE = load_module(
    "prepare_vba_movie", ROOT / "scripts/shiftcheck/tas/prepare_vba_movie.py"
)


class VbaFingerprintTests(unittest.TestCase):
    def test_collects_complete_gd_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            rom = out_dir / "game.gba"
            rom_data = bytearray(0xC0)
            rom_data[0xA0:0xAC] = b"FIREEMBLEM2E"
            rom_data[0xAC:0xB0] = b"BE8E"
            rom.write_bytes(rom_data)
            frames = COLLECTOR.checkpoint_frames(300, 3)
            (out_dir / "vanilla_manifest.txt").write_text(
                "\n".join(str(frame) for frame in frames) + "\n"
            )
            (out_dir / "vanilla_done.txt").write_text("reached=300 expected=300\n")
            for frame in frames:
                (out_dir / f"vanilla_{frame:07d}.gd").write_bytes(
                    f"frame-{frame}".encode()
                )

            result = COLLECTOR.collect(out_dir, "vanilla", 300, 3, rom)
            self.assertTrue(result["complete"])
            self.assertEqual(result["emulation_frames"], 300)
            self.assertEqual(result["checkpoint_frames"], [100, 200, 300])
            self.assertEqual(
                [item["sha256"] for item in result["checkpoints"]],
                [
                    hashlib.sha256(f"frame-{frame}".encode()).hexdigest()
                    for frame in frames
                ],
            )

    def test_compare_reports_first_divergent_checkpoint(self):
        baseline = {
            "schema_version": 1,
            "fingerprint_format": "vba-gd-v1",
            "expected_frames": 2,
            "emulation_frames": 2,
            "checkpoint_frames": [1, 2],
            "checkpoints": [
                {"frame": 1, "sha256": "a"},
                {"frame": 2, "sha256": "b"},
            ],
            "complete": True,
        }
        candidate = {
            **baseline,
            "checkpoints": [
                {"frame": 1, "sha256": "a"},
                {"frame": 2, "sha256": "c"},
            ],
        }
        complete, frames, divergences = COMPARE.compare(baseline, candidate)
        self.assertTrue(complete)
        self.assertEqual(frames, [1, 2])
        self.assertEqual(divergences, [(2, "b", "c")])

    def test_endpoint_policy_uses_final_checkpoint(self):
        baseline = {
            "expected_frames": 3,
            "checkpoints": [
                {"frame": 1, "sha256": "a"},
                {"frame": 3, "sha256": "end"},
            ],
        }
        candidate = {
            "expected_frames": 3,
            "checkpoints": [
                {"frame": 1, "sha256": "different"},
                {"frame": 3, "sha256": "end"},
            ],
        }
        self.assertEqual(
            COMPARE.endpoint_matches(baseline, candidate),
            (3, "end", "end", True),
        )

    def test_movie_guard_duplicates_last_input(self):
        data = bytearray(0x100 + 4)
        data[:4] = b"VBM\x1a"
        data[4:8] = (1).to_bytes(4, "little")
        data[12:16] = (2).to_bytes(4, "little")
        data[0x15] = 1
        data[0x3C:0x40] = (0x100).to_bytes(4, "little")
        data[0x100:0x104] = b"\x01\x00\x08\x00"

        guarded, original_frames = PREPARE.add_guard_frame(bytes(data))

        self.assertEqual(original_frames, 2)
        self.assertEqual(int.from_bytes(guarded[12:16], "little"), 3)
        self.assertEqual(guarded[0x100:0x106], b"\x01\x00\x08\x00\x08\x00")



if __name__ == "__main__":
    unittest.main()
