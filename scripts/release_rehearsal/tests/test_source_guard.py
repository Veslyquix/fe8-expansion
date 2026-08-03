"""Tests for scripts/release_rehearsal/source_guard.py (issue #9)."""

import io
import json
import os
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import source_guard as sg


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _init_git_repo(root: Path) -> None:
    """A minimal, throwaway git repo -- only ``git add`` (index staging)
    is required for ``git ls-files`` to see tracked files; no commit or
    configured identity is needed."""
    _git("init", "-q", cwd=root)


# --- Structural, prefix-tolerant ZIP fixture helpers (issue #9: prefixed/
# self-extracting ZIP detection) --------------------------------------
def _make_zip_bytes(entries, comment=b""):
    """A complete, valid, unprefixed ZIP byte blob with the given
    ``(name, data)`` entries and an optional archive comment."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries:
            zf.writestr(name, data)
        zf.comment = comment
    return buf.getvalue()


def _make_zip64_bytes(name="big.bin", data=b"x" * 100):
    """A structurally valid ZIP using an explicit Zip64 extension on its
    one entry (``force_zip64=True``), even though the entry itself is
    tiny -- Zip64 is a still-valid, still-prohibited ZIP structure under
    this policy, never a reason to skip/bypass detection."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", allowZip64=True) as zf:
        with zf.open(name, "w", force_zip64=True) as fh:
            fh.write(data)
    return buf.getvalue()


def _flip_general_purpose_bit(zip_bytes: bytes, bit: int) -> bytes:
    """Sets general-purpose flag `bit` (0 = traditional encryption; 3 =
    data-descriptor-follows) on the first entry's *local* file header
    and its matching *central directory* record. Flipping this bit alone
    never invalidates the archive's central-directory structure (sizes/
    CRC/offsets are untouched) -- it only changes how a real extractor
    would interpret payload bytes this guard never reads in the first
    place."""
    data = bytearray(zip_bytes)
    local_idx = data.find(b"PK\x03\x04")
    central_idx = data.find(b"PK\x01\x02")
    assert local_idx != -1 and central_idx != -1
    for idx, flag_offset in ((local_idx, local_idx + 6), (central_idx, central_idx + 8)):
        flag = struct.unpack_from("<H", data, flag_offset)[0]
        struct.pack_into("<H", data, flag_offset, flag | (1 << bit))
    return bytes(data)


def _corrupt_central_directory_signature(zip_bytes: bytes) -> bytes:
    """Flips one byte inside the *central directory* record's own
    ``PK\x01\x02`` signature while leaving the EOCD record (and its
    accurate ``size_cd``/``offset_cd`` fields) untouched -- a consistent,
    structurally-claimed-ZIP EOCD whose central directory itself then
    fails to parse (`zipfile.BadZipFile`: "Bad magic number for central
    directory"), i.e. the deliberate fail-closed "malformed" case."""
    data = bytearray(zip_bytes)
    idx = data.find(b"PK\x01\x02")
    assert idx != -1
    data[idx + 3] ^= 0xFF
    return bytes(data)


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

    # --- issue #9 verifier remediation: nested archive/executable magics ---

    def test_zip_magic(self):
        self.assertEqual(sg.classify_magic(b"PK\x03\x04" + b"\x00" * 20), "prohibited-magic-zip-archive")

    def test_zip_empty_archive_magic(self):
        self.assertEqual(sg.classify_magic(b"PK\x05\x06" + b"\x00" * 20), "prohibited-magic-zip-archive")

    def test_unix_ar_magic(self):
        self.assertEqual(sg.classify_magic(b"!<arch>\n" + b"\x00" * 20), "prohibited-magic-unix-ar-archive")

    def test_gzip_magic(self):
        self.assertEqual(sg.classify_magic(b"\x1f\x8b\x08\x00" + b"\x00" * 20), "prohibited-magic-gzip")

    def test_bzip2_magic(self):
        self.assertEqual(sg.classify_magic(b"BZh9" + b"\x00" * 20), "prohibited-magic-bzip2")

    def test_xz_magic(self):
        self.assertEqual(sg.classify_magic(b"\xfd7zXZ\x00" + b"\x00" * 20), "prohibited-magic-xz")

    def test_7z_magic(self):
        self.assertEqual(sg.classify_magic(b"7z\xbc\xaf\x27\x1c" + b"\x00" * 20), "prohibited-magic-7z")

    def test_rar_magic(self):
        self.assertEqual(sg.classify_magic(b"Rar!\x1a\x07\x00" + b"\x00" * 20), "prohibited-magic-rar")

    def test_zstd_magic(self):
        self.assertEqual(sg.classify_magic(b"\x28\xb5\x2f\xfd" + b"\x00" * 20), "prohibited-magic-zstd")

    def test_pe_exe_magic(self):
        self.assertEqual(sg.classify_magic(b"MZ\x90\x00" + b"\x00" * 20), "prohibited-magic-pe-executable")

    def test_macho_magic(self):
        self.assertEqual(
            sg.classify_magic(b"\xfe\xed\xfa\xcf" + b"\x00" * 20), "prohibited-magic-macho-executable"
        )

    def test_cafebabe_magic(self):
        self.assertEqual(
            sg.classify_magic(b"\xca\xfe\xba\xbe" + b"\x00" * 20), "prohibited-magic-macho-or-java-class"
        )

    def test_tar_ustar_magic(self):
        head = bytearray(512)
        head[257:262] = b"ustar"
        self.assertEqual(sg.classify_magic(bytes(head)), "prohibited-magic-tar-archive")

    def test_tar_gnu_ustar_magic(self):
        # GNU tar's variant is "ustar  \0" but the first 5 bytes are the
        # same "ustar" prefix this module keys on.
        head = bytearray(512)
        head[257:265] = b"ustar  \x00"
        self.assertEqual(sg.classify_magic(bytes(head)), "prohibited-magic-tar-archive")

    def test_misleading_extension_does_not_hide_zip_magic(self):
        """A ZIP smuggled under an innocuous ".txt"/".c" name must still be
        caught by content, not just by extension."""
        self.assertEqual(sg.classify_magic(b"PK\x03\x04" + b"\x00" * 40), "prohibited-magic-zip-archive")


class ZipStructureDetectionTests(unittest.TestCase):
    """`classify_zip_structure` (issue #9: structural, prefix-tolerant ZIP
    detection) operating directly on immutable ``bytes`` blobs -- the
    same code path filesystem files and tar members below both route
    through, per an in-memory `io.BytesIO` wrapper."""

    def test_unprefixed_valid_zip_detected(self):
        data = _make_zip_bytes([("hello.txt", b"hi")])
        self.assertEqual(sg.classify_zip_structure(data), "prohibited-magic-zip-archive")

    def test_prefixed_valid_zip_detected_various_prefix_lengths(self):
        """A valid ZIP is still a valid ZIP -- and still just as
        prohibited -- no matter how long an arbitrary prefix precedes it
        (a self-extracting archive's native stub is the canonical
        legitimate real-world example of exactly this shape)."""
        zip_bytes = _make_zip_bytes([("hello.txt", b"hi")])
        for prefix_len in (1, 2, 64, 4096, 65600):
            with self.subTest(prefix_len=prefix_len):
                prefixed = (b"P" * prefix_len) + zip_bytes
                self.assertEqual(
                    sg.classify_zip_structure(prefixed), "prohibited-magic-zip-archive"
                )

    def test_prefixed_zip_with_eocd_comment_detected(self):
        """A ZIP with a non-empty archive comment (itself part of a valid
        EOCD record) is still detected once prefixed."""
        zip_bytes = _make_zip_bytes([("hello.txt", b"hi")], comment=b"c" * 500)
        prefixed = b"SFX-STUB-BYTES" * 37 + zip_bytes
        self.assertEqual(sg.classify_zip_structure(prefixed), "prohibited-magic-zip-archive")

    def test_nested_zip_containing_prohibited_content_detected_regardless_of_prefix(self):
        """The inner ZIP's own entry content (here, an ELF payload) is
        irrelevant to detection -- the whole archive is denied outright
        by structure alone, exactly like an unprefixed nested ZIP is; no
        unwrapping/extraction of the inner entry is ever required or
        performed to reach this verdict."""
        zip_bytes = _make_zip_bytes([("payload.bin", b"\x7fELF" + b"\x00" * 32)])
        prefixed = b"\x00" * 4096 + zip_bytes
        self.assertEqual(sg.classify_zip_structure(prefixed), "prohibited-magic-zip-archive")

    def test_encrypted_flag_entry_still_detected_never_decrypted(self):
        zip_bytes = _flip_general_purpose_bit(_make_zip_bytes([("hello.txt", b"hi")]), bit=0)
        self.assertEqual(sg.classify_zip_structure(zip_bytes), "prohibited-magic-zip-archive")

    def test_data_descriptor_flag_entry_still_detected(self):
        zip_bytes = _flip_general_purpose_bit(_make_zip_bytes([("hello.txt", b"hi")]), bit=3)
        self.assertEqual(sg.classify_zip_structure(zip_bytes), "prohibited-magic-zip-archive")

    def test_zip64_entry_still_detected(self):
        self.assertEqual(sg.classify_zip_structure(_make_zip64_bytes()), "prohibited-magic-zip-archive")

    def test_ordinary_text_not_misclassified(self):
        data = b"just some ordinary C source code with no zip bytes at all\n" * 20
        self.assertIsNone(sg.classify_zip_structure(data))

    def test_stray_pk_bytes_without_eocd_not_misclassified(self):
        """Random `PK`-prefixed bytes with no consistent EOCD anywhere in
        the tail must remain ordinary data -- a naive substring/magic
        check would false-positive here; structural EOCD validation must
        not."""
        data = b"PK just some coincidental letters, not a real header" * 50
        self.assertIsNone(sg.classify_zip_structure(data))

    def test_truncated_zip_missing_eocd_not_misclassified(self):
        """Cutting off the tail of a real ZIP (destroying its EOCD
        record entirely) must never masquerade as a valid archive --
        with no EOCD signature present anywhere in the tail window at
        all, this is correctly ordinary (if truncated/corrupt) data, not
        a "claimed" ZIP to fail closed on."""
        zip_bytes = _make_zip_bytes([("hello.txt", b"hi")])
        self.assertIsNone(sg.classify_zip_structure(zip_bytes[: len(zip_bytes) - 30]))

    def test_malformed_central_directory_signature_fails_closed(self):
        """A consistent EOCD is present (the stream structurally *claims*
        to be a ZIP), but its own declared central directory is corrupt
        -- this must be denied (fail closed), never silently waved
        through as ordinary data just because it also turns out to be
        broken."""
        zip_bytes = _corrupt_central_directory_signature(_make_zip_bytes([("hello.txt", b"hi")]))
        self.assertEqual(
            sg.classify_zip_structure(zip_bytes), "prohibited-magic-zip-archive-malformed"
        )

    def test_malformed_truncated_central_directory_fails_closed(self):
        zip_bytes = _make_zip_bytes([("hello.txt", b"hi")])
        idx = zip_bytes.find(b"PK\x01\x02")
        # Remove 8 bytes from inside the central directory record while
        # leaving the EOCD record (and its size_cd/offset_cd fields --
        # now inconsistent with the shortened actual content) untouched.
        mutated = zip_bytes[: idx + 2] + zip_bytes[idx + 10 :]
        self.assertEqual(
            sg.classify_zip_structure(mutated), "prohibited-magic-zip-archive-malformed"
        )

    def test_too_short_to_be_a_zip_not_misclassified(self):
        self.assertIsNone(sg.classify_zip_structure(b"hi"))

    def test_accepts_bytearray_blob_too(self):
        zip_bytes = _make_zip_bytes([("hello.txt", b"hi")])
        self.assertEqual(
            sg.classify_zip_structure(bytearray(zip_bytes)), "prohibited-magic-zip-archive"
        )

    def test_accepts_open_seekable_file_object(self):
        """The same function, given an already-open seekable binary file
        object (as `_hard_deny_check_file`/`scan_archive_members` below
        both pass it) rather than a raw `bytes` blob, behaves
        identically -- this is the single shared code path both a
        filesystem file and a tar member route through."""
        zip_bytes = b"prefix-stub" * 10 + _make_zip_bytes([("hello.txt", b"hi")])
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "prefixed.bin"
            fixture.write_bytes(zip_bytes)
            with open(fixture, "rb") as handle:
                self.assertEqual(
                    sg.classify_zip_structure(handle), "prohibited-magic-zip-archive"
                )


class PathSegmentTests(unittest.TestCase):
    def test_prohibited_extension(self):
        self.assertIn("prohibited-extension", sg.classify_path_segments("foo/bar.gba"))

    def test_prohibited_path_segment(self):
        self.assertIn("prohibited-path-segment", sg.classify_path_segments("build/out.c"))

    def test_baserom_segment(self):
        self.assertIn("prohibited-baserom-path", sg.classify_path_segments("baserom.gba/x"))

    def test_clean_path(self):
        self.assertEqual(sg.classify_path_segments("src/main.c"), [])

    # --- issue #9 verifier remediation: expanded extension coverage ---

    def test_object_and_library_extensions(self):
        for ext in (".o", ".obj", ".a", ".lib", ".so", ".dll", ".dylib", ".exe", ".pdb"):
            with self.subTest(ext=ext):
                self.assertIn("prohibited-extension", sg.classify_path_segments(f"build/thing{ext}"))

    def test_versioned_shared_object_suffix(self):
        self.assertIn(
            "prohibited-versioned-shared-object", sg.classify_path_segments("lib/libfoo.so.1.2.3")
        )
        self.assertIn("prohibited-versioned-shared-object", sg.classify_path_segments("lib/libfoo.so.1"))

    def test_dsym_bundle_segment(self):
        self.assertIn(
            "prohibited-debug-symbol-bundle", sg.classify_path_segments("out/MyTool.dSYM/Contents/x")
        )

    def test_archive_container_extensions(self):
        for ext in (".zip", ".jar", ".war", ".ear", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar"):
            with self.subTest(ext=ext):
                self.assertIn("prohibited-extension", sg.classify_path_segments(f"dist/thing{ext}"))

    def test_tar_gz_compound_extension_denied(self):
        self.assertIn("prohibited-extension", sg.classify_path_segments("dist/thing.tar.gz"))

    def test_map_hex_default_denied(self):
        self.assertIn("prohibited-extension", sg.classify_path_segments("build/out.map"))
        self.assertIn("prohibited-extension", sg.classify_path_segments("build/out.hex"))

    def test_map_hex_exact_exception_allowed(self):
        exceptions = frozenset({"scripts/x/tests/fixtures/valid.map"})
        findings = sg.classify_path_segments("scripts/x/tests/fixtures/valid.map", exceptions)
        self.assertNotIn("prohibited-extension", findings)

    def test_map_hex_exception_is_exact_not_directory(self):
        """An exception for one exact file must never implicitly allow a
        sibling .map/.hex file in the same directory."""
        exceptions = frozenset({"scripts/x/tests/fixtures/valid.map"})
        findings = sg.classify_path_segments("scripts/x/tests/fixtures/other.map", exceptions)
        self.assertIn("prohibited-extension", findings)

    def test_map_hex_exception_does_not_suppress_other_prohibitions(self):
        """Excepting the extension check must never excuse an unrelated
        hard-deny finding (e.g. a prohibited path segment) for the same
        path."""
        exceptions = frozenset({"build/out.map"})
        findings = sg.classify_path_segments("build/out.map", exceptions)
        self.assertNotIn("prohibited-extension", findings)
        self.assertIn("prohibited-path-segment", findings)


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

    # --- issue #9 verifier remediation ---

    def test_double_slash(self):
        self.assertTrue(sg.is_unsafe_member_name("a//b"))

    def test_dot_component(self):
        self.assertTrue(sg.is_unsafe_member_name("a/./b"))

    def test_leading_slash(self):
        self.assertTrue(sg.is_unsafe_member_name("/a/b"))

    def test_trailing_slash(self):
        self.assertTrue(sg.is_unsafe_member_name("a/b/"))

    def test_tilde_prefixed(self):
        self.assertTrue(sg.is_unsafe_member_name("~root/.ssh/authorized_keys"))

    def test_control_character(self):
        self.assertTrue(sg.is_unsafe_member_name("a/b\x01c"))
        self.assertTrue(sg.is_unsafe_member_name("a/b\tc"))

    def test_single_dot_only_component(self):
        self.assertTrue(sg.is_unsafe_member_name("."))

    def test_double_dot_only_component(self):
        self.assertTrue(sg.is_unsafe_member_name(".."))

    def test_non_string_is_unsafe(self):
        self.assertTrue(sg.is_unsafe_member_name(None))  # type: ignore[arg-type]

    def test_safe_dotted_filename_not_flagged(self):
        """A literal '.' component is unsafe, but an ordinary filename
        that merely *contains* dots (not a bare '.' path segment) is
        perfectly safe and must not be flagged."""
        self.assertFalse(sg.is_unsafe_member_name("src/file.v2.3.c"))
        self.assertFalse(sg.is_unsafe_member_name(".clang-format"))


class LoadMapHexExceptionsTests(unittest.TestCase):
    def test_valid_exceptions_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map_hex_exceptions.json"
            path.write_text(json.dumps({
                "exceptions": [{"path": "a/b.map", "rationale": "synthetic test fixture"}]
            }), encoding="utf-8")
            exceptions = sg.load_map_hex_exceptions(path)
            self.assertEqual(exceptions, frozenset({"a/b.map"}))

    def test_empty_exceptions_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map_hex_exceptions.json"
            path.write_text(json.dumps({"exceptions": []}), encoding="utf-8")
            self.assertEqual(sg.load_map_hex_exceptions(path), frozenset())

    def test_missing_rationale_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map_hex_exceptions.json"
            path.write_text(json.dumps({"exceptions": [{"path": "a/b.map", "rationale": ""}]}), encoding="utf-8")
            with self.assertRaises(sg.SourceGuardError):
                sg.load_map_hex_exceptions(path)

    def test_non_map_hex_extension_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map_hex_exceptions.json"
            path.write_text(
                json.dumps({"exceptions": [{"path": "a/b.txt", "rationale": "not map/hex"}]}),
                encoding="utf-8",
            )
            with self.assertRaises(sg.SourceGuardError):
                sg.load_map_hex_exceptions(path)

    def test_duplicate_path_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map_hex_exceptions.json"
            path.write_text(json.dumps({"exceptions": [
                {"path": "a/b.map", "rationale": "one"},
                {"path": "a/b.map", "rationale": "two"},
            ]}), encoding="utf-8")
            with self.assertRaises(sg.SourceGuardError):
                sg.load_map_hex_exceptions(path)

    def test_real_exceptions_file_loads_and_matches_audit(self):
        exceptions = sg.load_map_hex_exceptions(
            ROOT / "docs" / "release_data" / "map_hex_exceptions.json"
        )
        self.assertEqual(len(exceptions), 12)
        for path in exceptions:
            self.assertTrue(path.endswith(".map") or path.endswith(".hex"))


class ScanTreeTests(unittest.TestCase):
    """issue #9 verifier remediation: `allowlist` is matched *exactly* --
    a bare top-level/directory name like `"src"` no longer authorizes
    anything nested under it. Every fixture below uses an exact per-file
    allowlist, matching the real docs/release_data/source_allowlist.json
    shape."""

    def test_not_allowlisted_top_level_closed_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "extra").mkdir()
            (root / "extra" / "payload.c").write_text("int payload;")
            violations = sg.scan_tree(root, {"src/main.c"})
            self.assertIn(("extra/payload.c", "not-allowlisted"), violations)

    def test_bare_directory_name_no_longer_authorizes_nested_files(self):
        """The pre-remediation defect, reproduced directly: `"src"` (a
        bare directory name, never itself a real tracked file) must NOT
        cover `"src/main.c"` any more -- both a ghost-style allowlist
        entry and a real "not-allowlisted" finding for the nested file."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            violations = sg.scan_tree(root, {"src"})
            self.assertIn(("src/main.c", "not-allowlisted"), violations)

    def test_known_file_allowed_unlisted_sibling_fails_closed_world(self):
        """`src/known.c` is allowlisted and produces no "not-allowlisted"
        finding; `src/unlisted.c`, sitting right next to it under the
        very same parent directory, is not allowlisted and must fail
        closed regardless."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "known.c").write_text("int known;")
            (root / "src" / "unlisted.c").write_text("int unlisted;")
            violations = sg.scan_tree(root, {"src/known.c"})
            self.assertNotIn(("src/known.c", "not-allowlisted"), violations)
            self.assertIn(("src/unlisted.c", "not-allowlisted"), violations)

    def test_deeply_nested_unlisted_file_fails_closed(self):
        """A new, unlisted member nested arbitrarily deep under an
        otherwise-allowlisted tree must still fail closed -- nesting
        depth is never a mitigating factor."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "known").mkdir(parents=True)
            (root / "src" / "known" / "main.c").write_text("int main(void){return 0;}")
            (root / "src" / "known" / "deep").mkdir()
            (root / "src" / "known" / "deep" / "unlisted.c").write_text("int unlisted;")
            violations = sg.scan_tree(root, {"src/known/main.c"})
            self.assertIn(("src/known/deep/unlisted.c", "not-allowlisted"), violations)

    def test_open_world_ignores_non_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "build").mkdir()
            (root / "build" / "out.o").write_bytes(b"junk")
            violations = sg.scan_tree(root, {"src/main.c"}, closed_world=False)
            self.assertEqual(violations, [])

    def test_open_world_never_reports_not_allowlisted_even_for_unlisted_sibling(self):
        """`closed_world=False` never reports "not-allowlisted" at all (it
        is only used to build archive content out of a live worktree,
        where anything not exactly allowlisted is simply irrelevant, not
        itself a violation) -- but every visited file is still fully
        hard-deny-checked."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "known.c").write_text("int known;")
            (root / "src" / "unlisted.c").write_text("int unlisted;")
            violations = sg.scan_tree(root, {"src/known.c"}, closed_world=False)
            self.assertEqual(violations, [])

    def test_nested_prohibited_extension_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "sneaky.gba").write_bytes(b"\x00" * 32)
            violations = sg.scan_tree(root, {"src/sneaky.gba"}, closed_world=False)
            self.assertIn(("src/sneaky.gba", "prohibited-extension"), violations)

    def test_nested_prohibited_magic_flagged_even_with_safe_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "innocuous.c").write_bytes(b"\x7fELF" + b"\x00" * 32)
            violations = sg.scan_tree(root, {"src/innocuous.c"}, closed_world=False)
            self.assertIn(("src/innocuous.c", "prohibited-magic-elf"), violations)

    def test_nested_zip_flagged_under_innocuous_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "notes.txt").write_bytes(b"PK\x03\x04" + b"\x00" * 32)
            violations = sg.scan_tree(root, {"src/notes.txt"}, closed_world=False)
            self.assertIn(("src/notes.txt", "prohibited-magic-zip-archive"), violations)

    def test_prefixed_zip_filesystem_file_detected(self):
        """issue #9: a valid ZIP with an arbitrary (nonzero-offset)
        prefix -- e.g. a self-extracting archive's native stub -- sitting
        directly as a real filesystem file must be caught by structural
        EOCD/central-directory detection, not just the offset-0 magic
        check, which would silently miss it (the file's own byte 0 is
        prefix data, never `PK\x03\x04`)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            zip_bytes = _make_zip_bytes([("hello.txt", b"hi")])
            prefixed = b"MZ-SFX-STUB-NOT-A-REAL-PE-JUST-A-PREFIX" * 20 + zip_bytes
            (root / "src" / "innocuous.dat").write_bytes(prefixed)
            self.assertNotEqual(prefixed[:4], b"PK\x03\x04")
            violations = sg.scan_tree(root, {"src/innocuous.dat"}, closed_world=False)
            self.assertIn(("src/innocuous.dat", "prohibited-magic-zip-archive"), violations)

    def test_prefixed_zip_containing_prohibited_content_filesystem_file_detected(self):
        """A prefixed ZIP whose own inner entry holds prohibited content
        (an ELF payload) is still denied as a whole by structure alone --
        detection never needs to (and never does) unpack the inner entry
        to reach this verdict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            inner_zip = _make_zip_bytes([("payload.bin", b"\x7fELF" + b"\x00" * 32)])
            prefixed = b"\x00" * 2048 + inner_zip
            (root / "src" / "asset.dat").write_bytes(prefixed)
            violations = sg.scan_tree(root, {"src/asset.dat"}, closed_world=False)
            self.assertIn(("src/asset.dat", "prohibited-magic-zip-archive"), violations)

    def test_malformed_prefixed_zip_filesystem_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            corrupted = _corrupt_central_directory_signature(_make_zip_bytes([("hello.txt", b"hi")]))
            prefixed = b"stub" * 50 + corrupted
            (root / "src" / "broken.dat").write_bytes(prefixed)
            violations = sg.scan_tree(root, {"src/broken.dat"}, closed_world=False)
            self.assertIn(("src/broken.dat", "prohibited-magic-zip-archive-malformed"), violations)

    def test_prefixed_zip_scan_never_extracts_to_disk(self):
        """Scanning a prefixed-ZIP filesystem file must never write any
        new file/directory anywhere -- structural detection is strictly
        read-only enumeration, never an extraction."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            zip_bytes = _make_zip_bytes([("hello.txt", b"hi"), ("nested/dir/entry.txt", b"x")])
            (root / "src" / "asset.dat").write_bytes(b"prefix" * 10 + zip_bytes)
            before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            sg.scan_tree(root, {"src/asset.dat"}, closed_world=False)
            after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            self.assertEqual(before, after)

    def test_double_slash_path_rejected_defense_in_depth(self):
        """scan_tree's own per-file check applies is_unsafe_member_name to
        every relative path it computes, as defense-in-depth (a real
        os.walk() never actually produces one, but the check is applied
        uniformly regardless)."""
        self.assertTrue(sg.is_unsafe_member_name("a//b"))

    def test_symlink_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            real = root / "src" / "real.c"
            real.write_text("int x;")
            link = root / "src" / "link.c"
            link.symlink_to(real)
            violations = sg.scan_tree(root, {"src/real.c", "src/link.c"}, closed_world=False)
            self.assertIn(("src/link.c", "prohibited-symlink"), violations)

    def test_symlink_to_directory_flagged_even_though_dirnames_are_structural_only(self):
        """A directory is a structural parent only and is never itself
        required to be an allowlist entry -- but a *symlink* to a
        directory is not a real directory, and must still be rejected as
        "prohibited-symlink" (os.walk(followlinks=False) lists it in
        `dirnames` without descending into it, so this exercises that
        exact code path). Uses `closed_world=True` (the "everything is
        walked" mode) -- `closed_world=False` deliberately never even
        visits a top-level entry with no relation to the allowlist at all
        (see its own docstring: "anything else present in root is
        silently irrelevant"), which is pre-existing, intentional
        behavior, not something this test is about."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_dir = root / "realdir"
            real_dir.mkdir()
            (real_dir / "main.c").write_text("int main(void){return 0;}")
            link_dir = root / "linkdir"
            link_dir.symlink_to(real_dir, target_is_directory=True)
            violations = sg.scan_tree(root, {"realdir/main.c"}, closed_world=True)
            self.assertIn(("linkdir", "prohibited-symlink"), violations)

    def test_hardlink_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            real = root / "src" / "real.c"
            real.write_text("int x;")
            hardlink = root / "src" / "hard.c"
            os.link(real, hardlink)
            violations = sg.scan_tree(root, {"src/real.c", "src/hard.c"}, closed_world=False)
            self.assertIn(("src/real.c", "prohibited-hardlink"), violations)
            self.assertIn(("src/hard.c", "prohibited-hardlink"), violations)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFOs not representable on this platform")
    def test_fifo_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            fifo_path = root / "src" / "pipe"
            os.mkfifo(fifo_path)
            violations = sg.scan_tree(root, {"src/pipe"}, closed_world=False)
            self.assertIn(("src/pipe", "prohibited-non-regular-file"), violations)

    def test_clean_tree_no_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            self.assertEqual(sg.scan_tree(root, {"src/main.c"}), [])

    def test_directories_are_never_flagged_themselves_only_files_are(self):
        """A real, non-symlink directory is walked through purely as a
        structural parent -- it is never itself checked for exact
        allowlist membership (only actual files ever are)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "nested").mkdir(parents=True)
            (root / "src" / "nested" / "main.c").write_text("int main(void){return 0;}")
            violations = sg.scan_tree(root, {"src/nested/main.c"})
            self.assertEqual(violations, [])

    def test_map_hex_exception_threaded_through_scan_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "fixture.map").write_text("Memory Configuration\n")
            violations_denied = sg.scan_tree(root, {"src/fixture.map"}, closed_world=False)
            self.assertIn(("src/fixture.map", "prohibited-extension"), violations_denied)
            violations_allowed = sg.scan_tree(
                root, {"src/fixture.map"}, closed_world=False, map_hex_exceptions=frozenset({"src/fixture.map"})
            )
            self.assertEqual(violations_allowed, [])


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

    def test_double_slash_member_flagged(self):
        tar = self._make_tar([("src//evil.c", b"int x;", tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("src//evil.c", "unsafe-member-name"), violations)

    def test_dot_component_member_flagged(self):
        tar = self._make_tar([("src/./evil.c", b"int x;", tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("src/./evil.c", "unsafe-member-name"), violations)

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
        violations = sg.scan_archive_members(tar, {"src/main.c"})
        self.assertIn(("evil/payload.c", "not-allowlisted"), violations)

    def test_bare_directory_name_no_longer_authorizes_nested_members(self):
        """The pre-remediation defect, reproduced directly against archive
        members: `"src"` (a bare directory-shaped allowlist entry) must
        NOT cover `"src/main.c"` any more."""
        tar = self._make_tar([("src/main.c", b"int main(void){return 0;}", tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src"})
        self.assertIn(("src/main.c", "not-allowlisted"), violations)

    def test_known_member_allowed_unlisted_sibling_fails(self):
        """`src/known.c` is allowlisted and produces no "not-allowlisted"
        finding; `src/unlisted.c`, sitting right next to it in the same
        archive directory, is not allowlisted and must fail closed."""
        tar = self._make_tar([
            ("src/known.c", b"int known;", tarfile.REGTYPE),
            ("src/unlisted.c", b"int unlisted;", tarfile.REGTYPE),
        ])
        violations = sg.scan_archive_members(tar, {"src/known.c"})
        self.assertNotIn(("src/known.c", "not-allowlisted"), violations)
        self.assertIn(("src/unlisted.c", "not-allowlisted"), violations)

    def test_deeply_nested_unlisted_member_fails_closed(self):
        """A new, unlisted member nested arbitrarily deep inside an
        otherwise-allowlisted archive directory must still fail closed."""
        tar = self._make_tar([
            ("src/known/main.c", b"int main(void){return 0;}", tarfile.REGTYPE),
            ("src/known/deep/unlisted.c", b"int unlisted;", tarfile.REGTYPE),
        ])
        violations = sg.scan_archive_members(tar, {"src/known/main.c"})
        self.assertIn(("src/known/deep/unlisted.c", "not-allowlisted"), violations)

    def test_directory_members_are_never_flagged_themselves(self):
        """A directory member is a structural parent only -- it is never
        itself required to be an exact allowlist entry."""
        tar = self._make_tar([("src/known.c", b"int known;", tarfile.REGTYPE)])
        # tarfile auto-adds no implicit directory members here, but the
        # scan must still never require "src" itself to be allowlisted.
        violations = sg.scan_archive_members(tar, {"src/known.c"})
        self.assertEqual(violations, [])

    def test_prohibited_content_flagged_without_extraction_to_disk(self):
        tar = self._make_tar([("src/sneaky.c", b"\x7fELF" + b"\x00" * 20, tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src/sneaky.c"})
        self.assertIn(("src/sneaky.c", "prohibited-magic-elf"), violations)

    def test_nested_zip_content_flagged_regardless_of_name(self):
        """A ZIP archive nested *as a member of this tar*, under an
        innocuous name, must still be rejected by content -- nested
        archives are rejected as content, not just by filename."""
        tar = self._make_tar([("src/innocent.c", b"PK\x03\x04" + b"\x00" * 20, tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src/innocent.c"})
        self.assertIn(("src/innocent.c", "prohibited-magic-zip-archive"), violations)

    def test_map_hex_default_denied_in_archive_member(self):
        tar = self._make_tar([("src/fireemblem8.map", b"Memory Configuration\n", tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src/fireemblem8.map"})
        self.assertIn(("src/fireemblem8.map", "prohibited-extension"), violations)

    def test_map_hex_exact_exception_allowed_in_archive_member(self):
        tar = self._make_tar([("src/fixture.map", b"Memory Configuration\n", tarfile.REGTYPE)])
        violations = sg.scan_archive_members(
            tar, {"src/fixture.map"}, map_hex_exceptions=frozenset({"src/fixture.map"})
        )
        self.assertEqual(violations, [])

    def test_clean_archive_no_violations(self):
        tar = self._make_tar([("src/main.c", b"int main(void){return 0;}", tarfile.REGTYPE)])
        self.assertEqual(sg.scan_archive_members(tar, {"src/main.c"}), [])

    def test_prefixed_zip_tar_member_detected(self):
        """issue #9: a valid ZIP with an arbitrary prefix, embedded as a
        tar member's own content under an innocuous name/extension, must
        be caught by structural EOCD/central-directory detection just
        like the offset-0 nested-ZIP case already is above."""
        zip_bytes = _make_zip_bytes([("hello.txt", b"hi")])
        prefixed = b"SFX-STUB-BYTES" * 30 + zip_bytes
        self.assertNotEqual(prefixed[:4], b"PK\x03\x04")
        tar = self._make_tar([("src/innocuous.dat", prefixed, tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src/innocuous.dat"})
        self.assertIn(("src/innocuous.dat", "prohibited-magic-zip-archive"), violations)

    def test_prefixed_zip_containing_prohibited_content_tar_member_detected(self):
        """A prefixed ZIP tar member whose own inner entry holds
        prohibited content (an ELF payload) is still denied as a whole by
        structure alone -- no unpacking of the inner entry is required or
        performed."""
        inner_zip = _make_zip_bytes([("payload.bin", b"\x7fELF" + b"\x00" * 32)])
        prefixed = b"\x00" * 2048 + inner_zip
        tar = self._make_tar([("src/asset.dat", prefixed, tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src/asset.dat"})
        self.assertIn(("src/asset.dat", "prohibited-magic-zip-archive"), violations)

    def test_malformed_prefixed_zip_tar_member_fails_closed(self):
        corrupted = _corrupt_central_directory_signature(_make_zip_bytes([("hello.txt", b"hi")]))
        prefixed = b"stub" * 40 + corrupted
        tar = self._make_tar([("src/broken.dat", prefixed, tarfile.REGTYPE)])
        violations = sg.scan_archive_members(tar, {"src/broken.dat"})
        self.assertIn(("src/broken.dat", "prohibited-magic-zip-archive-malformed"), violations)

    def test_prefixed_zip_tar_scan_never_extracts_to_disk(self):
        """Scanning a tar containing a prefixed-ZIP member must never
        write any file/directory anywhere on disk -- only
        `TarFile.extractfile()`'s own bounded, read-only, in-memory
        member stream is ever used."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            zip_bytes = _make_zip_bytes([("hello.txt", b"hi"), ("nested/dir/entry.txt", b"x")])
            tar = self._make_tar([("src/asset.dat", b"prefix" * 10 + zip_bytes, tarfile.REGTYPE)])
            before = sorted(p.relative_to(cwd).as_posix() for p in cwd.rglob("*"))
            sg.scan_archive_members(tar, {"src/asset.dat"})
            after = sorted(p.relative_to(cwd).as_posix() for p in cwd.rglob("*"))
            self.assertEqual(before, after)

    def test_multiple_prefix_lengths_and_comment_lengths_in_tar_member(self):
        base_zip = _make_zip_bytes([("hello.txt", b"hi")])
        commented_zip = _make_zip_bytes([("hello.txt", b"hi")], comment=b"c" * 1000)
        cases = [
            (0, base_zip),
            (1, base_zip),
            (777, base_zip),
            (0, commented_zip),
            (500, commented_zip),
        ]
        for prefix_len, zip_bytes in cases:
            with self.subTest(prefix_len=prefix_len, comment_len=len(zip_bytes)):
                name = f"src/case_{prefix_len}_{len(zip_bytes)}.dat"
                content = (b"P" * prefix_len) + zip_bytes
                tar = self._make_tar([(name, content, tarfile.REGTYPE)])
                violations = sg.scan_archive_members(tar, {name})
                self.assertIn((name, "prohibited-magic-zip-archive"), violations)


class GitTrackedAllowlistedFilesTests(unittest.TestCase):
    """`git_tracked_allowlisted_files` now matches the allowlist *exactly*
    (issue #9 verifier remediation: exact per-member allowlist, not
    top-level-directory grants) -- every fixture below uses exact file
    paths in its allowlist, matching the real
    docs/release_data/source_allowlist.json's shape."""

    def test_non_git_tree_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int x;")
            self.assertIsNone(sg.git_tracked_allowlisted_files(root, {"src/main.c"}))

    def test_git_tree_returns_only_tracked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            _git("add", "src/main.c", cwd=root)
            # Untracked sibling in the same allowlisted directory must be
            # excluded even though it is on disk.
            (root / "src" / "untracked.c").write_text("int untracked;")
            files = sg.git_tracked_allowlisted_files(root, {"src/main.c"})
            relpaths = sorted(p.relative_to(root).as_posix() for p in files)
            self.assertEqual(relpaths, ["src/main.c"])

    def test_git_tree_excludes_tracked_files_outside_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "other").mkdir()
            (root / "other" / "extra.c").write_text("int extra;")
            _git("add", "src/main.c", "other/extra.c", cwd=root)
            files = sg.git_tracked_allowlisted_files(root, {"src/main.c"})
            relpaths = sorted(p.relative_to(root).as_posix() for p in files)
            self.assertEqual(relpaths, ["src/main.c"])

    def test_exact_match_excludes_unlisted_new_file_under_allowlisted_directory(self):
        """The core issue #9 gap this closes: a *new* tracked file sitting
        in an otherwise-allowlisted directory must NOT be silently
        included just because a sibling file in that directory is
        allowlisted -- exact membership is required per file."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "src" / "new_unreviewed.c").write_text("int new_unreviewed;")
            _git("add", "-A", cwd=root)
            files = sg.git_tracked_allowlisted_files(root, {"src/main.c"})
            relpaths = sorted(p.relative_to(root).as_posix() for p in files)
            self.assertEqual(relpaths, ["src/main.c"])
            self.assertNotIn("src/new_unreviewed.c", relpaths)

    def test_gitlink_directory_excluded_from_tracked_files(self):
        """A submodule gitlink path (e.g. "mgfembp") is excluded from the
        returned file list even when explicitly allowlisted -- its
        content is never enumerated this way (see
        docs/release_process.md's submodule/provenance boundary)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            nested = Path(tmp) / "nested-submodule-repo"
            nested.mkdir()
            _git("init", "-q", cwd=nested)
            (nested / "f.txt").write_text("x")
            _git("add", "-A", cwd=nested)
            _git("-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "x", cwd=nested)
            nested_sha = _git("rev-parse", "HEAD", cwd=nested).strip()
            _git("update-index", "--add", "--cacheinfo", f"160000,{nested_sha},vendor", cwd=root)
            # Git always creates the submodule mountpoint directory on disk
            # (empty when uninitialized, exactly like this real
            # repository's own "mgfembp"); replicate that here rather than
            # leaving "vendor" entirely absent from the working tree.
            (root / "vendor").mkdir()
            files = sg.git_tracked_allowlisted_files(root, {"vendor"})
            self.assertEqual(files, [])


class ScanSourceReleaseCandidateTests(unittest.TestCase):
    """Regression coverage for the reviewer-reproduced trust defect: a git
    worktree manifest/source_guard check must evaluate the tracked-
    intersect-allowlist candidate set (consistent with
    scripts/release_rehearsal/archive_rehearsal.py), never a raw
    closed-world filesystem walk of a live, possibly-messy development
    worktree."""

    def test_untracked_gitignored_dot_dep_and_elf_ignored_in_git_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            _git("add", "src/main.c", cwd=root)

            # Stray gitignored/untracked build byproducts a live worktree
            # routinely contains: a .dep/ directory and a built ELF, both
            # sitting at the top level (outside the allowlisted "src"
            # entry) and therefore prohibited if this were a closed-world
            # scan -- but they are host/build state, not the source
            # release candidate, and must never affect this report.
            (root / ".dep").mkdir()
            (root / ".dep" / "main.o.d").write_text("main.o: src/main.c\n")
            (root / "fireemblem8.elf").write_bytes(b"\x7fELF" + b"\x00" * 32)

            violations = sg.scan_source_release_candidate(root, {"src/main.c"})
            self.assertEqual(violations, [])

    def test_tracked_prohibited_extension_violation_still_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "src" / "bad.gba").write_bytes(b"\x00" * 16)
            _git("add", "src/main.c", "src/bad.gba", cwd=root)

            violations = sg.scan_source_release_candidate(root, {"src/main.c", "src/bad.gba"})
            self.assertIn(("src/bad.gba", "prohibited-extension"), violations)

    def test_tracked_prohibited_magic_violation_still_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "innocuous.c").write_bytes(b"\x7fELF" + b"\x00" * 32)
            _git("add", "src/innocuous.c", cwd=root)

            violations = sg.scan_source_release_candidate(root, {"src/innocuous.c"})
            self.assertIn(("src/innocuous.c", "prohibited-magic-elf"), violations)

    def test_tracked_symlink_violation_still_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "src").mkdir()
            real = root / "src" / "real.c"
            real.write_text("int x;")
            link = root / "src" / "link.c"
            link.symlink_to(real)
            _git("add", "-A", "src", cwd=root)

            violations = sg.scan_source_release_candidate(root, {"src/real.c", "src/link.c"})
            self.assertIn(("src/link.c", "prohibited-symlink"), violations)

    def test_untracked_only_repo_with_no_tracked_files_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "build").mkdir()
            (root / "build" / "out.o").write_bytes(b"junk")
            # Nothing staged/tracked at all yet.
            violations = sg.scan_source_release_candidate(root, {"src/main.c"})
            self.assertEqual(violations, [])

    def test_non_git_tree_closed_world_rejects_extra_top_level_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "extra").mkdir()
            (root / "extra" / "payload.c").write_text("int payload;")
            violations = sg.scan_source_release_candidate(root, {"src/main.c"})
            self.assertIn(("extra/payload.c", "not-allowlisted"), violations)

    def test_non_git_tree_closed_world_rejects_nested_unsafe_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "sneaky.gba").write_bytes(b"\x00" * 32)
            violations = sg.scan_source_release_candidate(root, {"src/sneaky.gba"})
            self.assertIn(("src/sneaky.gba", "prohibited-extension"), violations)

    def test_non_git_tree_closed_world_rejects_unlisted_sibling_of_known_file(self):
        """issue #9 exact-provenance/source-guard remediation, reproduced
        against the actual `scan_source_release_candidate` entry point: a
        bare directory-shaped allowlist entry (`"src"`) must not silently
        authorize a new, unlisted sibling file placed right next to a
        genuinely allowlisted one."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "known.c").write_text("int known;")
            (root / "src" / "unlisted.c").write_text("int unlisted;")
            violations = sg.scan_source_release_candidate(root, {"src/known.c"})
            self.assertNotIn(("src/known.c", "not-allowlisted"), violations)
            self.assertIn(("src/unlisted.c", "not-allowlisted"), violations)

    def test_non_git_tree_clean_candidate_has_no_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            violations = sg.scan_source_release_candidate(root, {"src/main.c"})
            self.assertEqual(violations, [])

    def test_map_hex_exceptions_threaded_through_git_worktree_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_git_repo(root)
            (root / "tests" / "fixtures").mkdir(parents=True)
            fixture = root / "tests" / "fixtures" / "sample.map"
            fixture.write_text("Memory Configuration\n")
            _git("add", "-A", cwd=root)

            denied = sg.scan_source_release_candidate(root, {"tests/fixtures/sample.map"})
            self.assertIn(("tests/fixtures/sample.map", "prohibited-extension"), denied)

            allowed = sg.scan_source_release_candidate(
                root, {"tests/fixtures/sample.map"},
                map_hex_exceptions=frozenset({"tests/fixtures/sample.map"}),
            )
            self.assertEqual(allowed, [])


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
        self.assertEqual(len(allowlist), len(set(allowlist)))

    def test_real_allowlist_excludes_mgfembp_gitlink(self):
        """schema_version 3 / issue #9 mandatory correction #2: the
        `mgfembp` gitlink is now an explicit export-exclusion (see
        docs/release_data/export_exclusions.json and
        scripts/release_rehearsal/tests/test_tree_coverage.py), never an
        allowlist ("included") entry."""
        allowlist = sg.load_allowlist(ROOT / "docs" / "release_data" / "source_allowlist.json")
        self.assertNotIn("mgfembp", allowlist)

    def test_real_allowlist_is_exact_per_file_not_top_level_directories(self):
        """issue #9 verifier remediation: the checked-in allowlist must be
        the new exact per-member shape (thousands of exact file paths),
        never the old handful of bare top-level directory names."""
        allowlist = sg.load_allowlist(ROOT / "docs" / "release_data" / "source_allowlist.json")
        self.assertGreater(len(allowlist), 1000)
        self.assertIn("scripts/release_rehearsal/source_guard.py", allowlist)
        self.assertNotIn("src", allowlist)  # bare top-level directory name, not a file

    def test_real_map_hex_exceptions_file_loads(self):
        exceptions = sg.load_map_hex_exceptions(ROOT / "docs" / "release_data" / "map_hex_exceptions.json")
        self.assertEqual(len(exceptions), 12)


if __name__ == "__main__":
    unittest.main()
