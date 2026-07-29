"""Tests for scripts/release_rehearsal/source_guard.py (issue #9)."""

import io
import json
import os
import stat
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import source_guard as sg


class MagicClassificationTests(unittest.TestCase):
    def test_elf_magic(self):
        self.assertEqual(sg.classify_magic(b"\x7fELF" + b"\x00" * 20), "prohibited-magic-elf")

    def test_ips_magic(self):
        self.assertEqual(sg.classify_magic(b"PATCH" + b"\x00" * 20), "prohibited-magic-ips-patch")

    def test_gba_header_magic(self):
        head = bytearray(0xB3)
        head[4:20] = sg.GBA_LOGO_PREFIX
        head[0xB2] = 0x96
        self.assertEqual(sg.classify_magic(bytes(head)), "prohibited-magic-gba-header")

    def test_clean_bytes_no_classification(self):
        self.assertIsNone(sg.classify_magic(b"just plain text source code"))


class PathSegmentTests(unittest.TestCase):
    def test_prohibited_extension(self):
        self.assertIn("prohibited-extension", sg.classify_path_segments("foo/bar.gba"))

    def test_prohibited_path_segment(self):
        self.assertIn("prohibited-path-segment", sg.classify_path_segments("build/out.c"))

    def test_baserom_segment(self):
        self.assertIn("prohibited-baserom-path", sg.classify_path_segments("baserom.gba/x"))

    def test_clean_path(self):
        self.assertEqual(sg.classify_path_segments("src/main.c"), [])


class UnsafeMemberNameTests(unittest.TestCase):
    def test_absolute_path(self):
        self.assertTrue(sg.is_unsafe_member_name("/etc/passwd"))

    def test_traversal_path(self):
        self.assertTrue(sg.is_unsafe_member_name("../../etc/passwd"))
        self.assertTrue(sg.is_unsafe_member_name("src/../../etc/passwd"))

    def test_nul_byte(self):
        self.assertTrue(sg.is_unsafe_member_name("src/evil\x00.c"))

    def test_backslash(self):
        self.assertTrue(sg.is_unsafe_member_name("src\\evil.c"))

    def test_empty_name(self):
        self.assertTrue(sg.is_unsafe_member_name(""))

    def test_safe_relative_path(self):
        self.assertFalse(sg.is_unsafe_member_name("src/main.c"))


class ScanTreeTests(unittest.TestCase):
    def test_not_allowlisted_top_level_closed_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "extra").mkdir()
            violations = sg.scan_tree(root, {"src"})
            self.assertIn(("extra", "not-allowlisted"), violations)

    def test_open_world_ignores_non_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "build").mkdir()
            (root / "build" / "out.o").write_bytes(b"junk")
            violations = sg.scan_tree(root, {"src"}, closed_world=False)
            self.assertEqual(violations, [])

    def test_nested_prohibited_extension_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "sneaky.gba").write_bytes(b"\x00" * 32)
            violations = sg.scan_tree(root, {"src"}, closed_world=False)
            self.assertIn(("src/sneaky.gba", "prohibited-extension"), violations)

    def test_nested_prohibited_magic_flagged_even_with_safe_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "innocuous.c").write_bytes(b"\x7fELF" + b"\x00" * 32)
            violations = sg.scan_tree(root, {"src"}, closed_world=False)
            self.assertIn(("src/innocuous.c", "prohibited-magic-elf"), violations)

    def test_symlink_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            real = root / "src" / "real.c"
            real.write_text("int x;")
            link = root / "src" / "link.c"
            link.symlink_to(real)
            violations = sg.scan_tree(root, {"src"}, closed_world=False)
            self.assertIn(("src/link.c", "prohibited-symlink"), violations)

    def test_hardlink_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            real = root / "src" / "real.c"
            real.write_text("int x;")
            hardlink = root / "src" / "hard.c"
            os.link(real, hardlink)
            violations = sg.scan_tree(root, {"src"}, closed_world=False)
            self.assertIn(("src/real.c", "prohibited-hardlink"), violations)
            self.assertIn(("src/hard.c", "prohibited-hardlink"), violations)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFOs not representable on this platform")
    def test_fifo_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            fifo_path = root / "src" / "pipe"
            os.mkfifo(fifo_path)
            violations = sg.scan_tree(root, {"src"}, closed_world=False)
            self.assertIn(("src/pipe", "prohibited-non-regular-file"), violations)

    def test_clean_tree_no_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            self.assertEqual(sg.scan_tree(root, {"src"}), [])


class ScanArchiveMembersTests(unittest.TestCase):
    def _make_tar(self, members):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            for name, data, member_type in members:
                info = tarfile.TarInfo(name=name)
                if member_type == tarfile.REGTYPE:
                    info.size = len(data)
                    info.type = tarfile.REGTYPE
                    tar.addfile(info, io.BytesIO(data))
                elif member_type == tarfile.SYMTYPE:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "some/target"
                    tar.addfile(info)
                elif member_type == tarfile.CHRTYPE:
                    info.type = tarfile.CHRTYPE
                    tar.addfile(info)
        buffer.seek(0)
        return tarfile.open(fileobj=buffer, mode="r")

    def test_traversal_member_flagged(self):
        tar = self._make_tar([("../evil.c", b"int x;", tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("../evil.c", "unsafe-member-name"), violations)

    def test_absolute_member_flagged(self):
        tar = self._make_tar([("/etc/passwd", b"root:x", tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("/etc/passwd", "unsafe-member-name"), violations)

    def test_symlink_member_flagged(self):
        tar = self._make_tar([("src/link.c", b"", tarfile.SYMTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("src/link.c", "prohibited-link-member"), violations)

    def test_device_member_flagged(self):
        tar = self._make_tar([("src/dev", b"", tarfile.CHRTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("src/dev", "prohibited-device-member"), violations)

    def test_not_allowlisted_top_level_flagged(self):
        tar = self._make_tar([("evil/payload.c", b"int x;", tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("evil/payload.c", "not-allowlisted"), violations)

    def test_prohibited_content_flagged_without_extraction_to_disk(self):
        tar = self._make_tar([("src/sneaky.c", b"\x7fELF" + b"\x00" * 20, tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("src/sneaky.c", "prohibited-magic-elf"), violations)

    def test_clean_archive_no_violations(self):
        tar = self._make_tar([("src/main.c", b"int main(void){return 0;}", tarfile.REGTYPE)])
        self.assertEqual(sg.scan_archive_members(tar, {"src"}), [])


class LoadAllowlistTests(unittest.TestCase):
    def test_valid_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.json"
            path.write_text(json.dumps({"paths": ["src", "docs"]}), encoding="utf-8")
            self.assertEqual(sg.load_allowlist(path), ["src", "docs"])

    def test_empty_paths_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.json"
            path.write_text(json.dumps({"paths": []}), encoding="utf-8")
            with self.assertRaises(sg.SourceGuardError):
                sg.load_allowlist(path)

    def test_missing_paths_key_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            with self.assertRaises(sg.SourceGuardError):
                sg.load_allowlist(path)


class RepositoryStateTests(unittest.TestCase):
    def test_real_allowlist_loads(self):
        allowlist = sg.load_allowlist(ROOT / "docs" / "release_data" / "source_allowlist.json")
        self.assertIn("src", allowlist)
        self.assertIn("mgfembp", allowlist)
        self.assertEqual(len(allowlist), len(set(allowlist)))


if __name__ == "__main__":
    unittest.main()
