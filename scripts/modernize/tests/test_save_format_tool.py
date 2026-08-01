"""Tests for scripts/modernize/save_format_tool.py (issue #2 slice 1).

Covers checksum16()'s exact algorithm, is_region_blank(), every one of the
8 SaveCompatState classifications and their precedence, that diagnostic
fields (abiId/frameworkVersionPacked/configFingerprint/buildCommitShort)
never influence classification, the migrate CLI's exit codes (success,
precondition failure with source preservation, source==destination
refusal), and the validate CLI's --expect handling.

All fixtures are synthetic byte arrays built in memory -- no committed
binary blobs, ROM dumps, or savestates, per issue #2 slice 1's guardrails.
"""

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))

import save_format_tool as sft  # noqa: E402


# --- Synthetic fixture builders ----------------------------------------------


def make_header(valid: bool = True) -> bytearray:
    """Builds a struct GlobalSaveInfo-shaped region (0x64 bytes)."""
    header = bytearray(sft.HEADER_SIZE)
    if valid:
        header[0:8] = sft.HEADER_NAME_MARKER
        header[8:12] = sft.SAVEMAGIC32.to_bytes(4, "little")
        header[12:14] = sft.SAVEMAGIC16.to_bytes(2, "little")
        checksum = sft.checksum16(bytes(header[: sft.HEADER_CHECKSUM_DOMAIN]))
        header[0x60:0x62] = checksum.to_bytes(2, "little")
    else:
        header[0:8] = b"garbage!"
    return header


def make_meta(
    present: bool = True,
    format_version: int = sft.SAVE_FORMAT_VERSION_CURRENT,
    compat_epoch: int = 1,
    abi_id: int = sft.SAVE_ABI_ID_AAPCS,
    framework_version_packed: int = 0x000100,
    config_fingerprint: bytes = b"deadbeefcafebabe\x00",
    build_commit_short: bytes = b"cafef00d\x00",
    corrupt_checksum: bool = False,
) -> bytearray:
    """Builds a struct ExpansionSaveMeta-shaped region (0x5C bytes)."""
    if not present:
        return bytearray([0xFF] * sft.META_SIZE)

    meta = sft.ExpansionSaveMeta(
        magic=sft.META_MAGIC,
        format_version=format_version,
        compat_epoch=compat_epoch,
        abi_id=abi_id,
        framework_version_packed=framework_version_packed,
        config_fingerprint=config_fingerprint,
        build_commit_short=build_commit_short,
        checksum=0,
        reserved=b"\x00" * (sft.META_SIZE - sft.META_CHECKSUM_DOMAIN - 2),
    )
    meta.checksum = meta.computed_checksum()
    if corrupt_checksum:
        meta.checksum ^= 0xFFFF
    return bytearray(meta.pack())


def make_image(header: bytes, meta: bytes, blank: bool = False) -> bytearray:
    if blank:
        image = bytearray([0xFF] * sft.SRAM_SIZE)
    else:
        image = bytearray(b"\x00" * sft.SRAM_SIZE)
    image[sft.HEADER_OFFSET : sft.HEADER_OFFSET + sft.HEADER_SIZE] = header
    image[sft.META_OFFSET : sft.META_OFFSET + sft.META_SIZE] = meta
    return image


# --- Checksum16 / blank-scan unit tests --------------------------------------


class Checksum16Tests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(sft.checksum16(b""), 0)

    def test_single_word(self):
        # add_acc = 0x1234, xor_acc = 0x1234 -> sum = 0x2468
        self.assertEqual(sft.checksum16(b"\x34\x12"), 0x2468)

    def test_two_words_add_and_xor_combine(self):
        # words: 0x1234, 0x0001
        # add_acc = 0x1235, xor_acc = 0x1235 (0x1234 ^ 0x0001) -> sum = 0x246A
        data = b"\x34\x12\x01\x00"
        self.assertEqual(sft.checksum16(data), 0x246A)

    def test_add_accumulator_wraps_at_32_bits(self):
        # Two words of 0xFFFF: add_acc wraps only past 2**32, so with only two
        # words it is simply 0x1FFFE; xor_acc of 0xFFFF ^ 0xFFFF == 0.
        data = b"\xff\xff\xff\xff"
        expected = (0x1FFFE + 0) & 0xFFFF
        self.assertEqual(sft.checksum16(data), expected)

    def test_matches_struct_pack_round_trip(self):
        # Sanity: checksum16 computed over a packed-then-zeroed-checksum
        # metadata record equals the record's own computed_checksum().
        meta_bytes = make_meta()
        meta = sft.ExpansionSaveMeta.unpack(bytes(meta_bytes))
        self.assertEqual(meta.checksum, sft.checksum16(bytes(meta_bytes)[: sft.META_CHECKSUM_DOMAIN]))


class IsRegionBlankTests(unittest.TestCase):
    def test_all_ff_is_blank(self):
        self.assertTrue(sft.is_region_blank(b"\xff" * 16))

    def test_any_non_ff_byte_is_not_blank(self):
        self.assertFalse(sft.is_region_blank(b"\xff" * 15 + b"\x00"))

    def test_empty_region_is_vacuously_blank(self):
        self.assertTrue(sft.is_region_blank(b""))


# --- Classifier precedence tests ---------------------------------------------


class ClassifySaveCompatRawTests(unittest.TestCase):
    EPOCH = 1

    def classify(self, header: bytes, meta: bytes) -> str:
        return sft.classify_save_compat_raw(bytes(header), bytes(meta), self.EPOCH)

    def test_blank_header_and_meta_is_empty(self):
        header = bytearray([0xFF] * sft.HEADER_SIZE)
        meta = bytearray([0xFF] * sft.META_SIZE)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_EMPTY)

    def test_valid_header_blank_meta_is_valid_legacy_or_vanilla(self):
        header = make_header(valid=True)
        meta = make_meta(present=False)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_VALID_LEGACY_OR_VANILLA)

    def test_invalid_nonblank_header_is_header_corrupt(self):
        header = make_header(valid=False)
        meta = make_meta(present=False)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_HEADER_CORRUPT)

    def test_valid_header_bad_header_checksum_is_header_corrupt(self):
        header = make_header(valid=True)
        header[0x60] ^= 0xFF  # corrupt the stored checksum only
        meta = make_meta(present=False)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_HEADER_CORRUPT)

    def test_metadata_checksum_mismatch_is_metadata_corrupt(self):
        header = make_header(valid=True)
        meta = make_meta(corrupt_checksum=True)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_METADATA_CORRUPT)

    def test_current_format_and_epoch_is_current(self):
        header = make_header(valid=True)
        meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT, compat_epoch=self.EPOCH)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_CURRENT)

    def test_older_format_version_is_migratable_older(self):
        header = make_header(valid=True)
        meta = make_meta(format_version=0, compat_epoch=self.EPOCH)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_MIGRATABLE_OLDER)

    def test_newer_format_version_is_newer_unsupported(self):
        header = make_header(valid=True)
        meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT + 1, compat_epoch=self.EPOCH)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_NEWER_UNSUPPORTED)

    def test_compat_epoch_mismatch_is_save_config_incompatible(self):
        header = make_header(valid=True)
        meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT, compat_epoch=self.EPOCH + 1)
        self.assertEqual(self.classify(header, meta), sft.SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE)

    def test_diagnostic_field_differences_never_change_classification(self):
        """abiId/frameworkVersionPacked/configFingerprint/buildCommitShort
        must never gate compatibility -- only magic/formatVersion/
        compatEpoch may (issue #2 slice 1 DON'T guardrail)."""
        header = make_header(valid=True)
        baseline = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT,
            compat_epoch=self.EPOCH,
            abi_id=sft.SAVE_ABI_ID_AAPCS,
            framework_version_packed=0x000100,
            config_fingerprint=b"aaaaaaaaaaaaaaaa\x00",
            build_commit_short=b"11111111\x00",
        )
        different_diagnostics = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT,
            compat_epoch=self.EPOCH,
            abi_id=sft.SAVE_ABI_ID_APCS_GNU,
            framework_version_packed=0x020304,
            config_fingerprint=b"ffffffffffffffff\x00",
            build_commit_short=b"deadbeef\x00",
        )
        self.assertEqual(self.classify(header, baseline), sft.SAVE_COMPAT_CURRENT)
        self.assertEqual(self.classify(header, different_diagnostics), sft.SAVE_COMPAT_CURRENT)

    def test_wrong_size_regions_raise(self):
        with self.assertRaises(sft.SaveFormatError):
            sft.classify_save_compat_raw(b"\x00" * 4, bytes(make_meta()), self.EPOCH)
        with self.assertRaises(sft.SaveFormatError):
            sft.classify_save_compat_raw(bytes(make_header()), b"\x00" * 4, self.EPOCH)


class ClassifyImageTests(unittest.TestCase):
    def test_full_image_wrong_size_raises(self):
        with self.assertRaises(sft.SaveFormatError):
            sft.classify_image(b"\x00" * 100, 1)

    def test_full_image_extracts_correct_regions(self):
        header = make_header(valid=True)
        meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT, compat_epoch=1)
        image = make_image(header, meta)
        self.assertEqual(sft.classify_image(bytes(image), 1), sft.SAVE_COMPAT_CURRENT)


# --- CLI tests ------------------------------------------------------------


class CliValidateTests(unittest.TestCase):
    def run_cli(self, *args) -> int:
        return sft.main(list(args))

    def test_validate_current_passes_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.bin"
            header = make_header(valid=True)
            # This CLI invocation resolves --repo-root's *real* config.mk
            # epoch (unlike ClassifySaveCompatRawTests above, which pins
            # a synthetic self.EPOCH and calls the pure classifier
            # directly) -- so the fixture must use that same real epoch,
            # not an arbitrary literal, to be classified CURRENT.
            real_epoch = sft.resolve_save_compat_epoch(ROOT)
            meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT, compat_epoch=real_epoch)
            path.write_bytes(bytes(make_image(header, meta)))
            self.assertEqual(
                self.run_cli("--repo-root", str(ROOT), "validate", str(path)), 0
            )

    def test_validate_unexpected_state_fails_with_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.bin"
            path.write_bytes(bytes([0xFF] * sft.SRAM_SIZE))  # EMPTY
            self.assertEqual(
                self.run_cli("--repo-root", str(ROOT), "validate", str(path)), 3
            )

    def test_validate_accepts_explicit_expect_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.bin"
            path.write_bytes(bytes([0xFF] * sft.SRAM_SIZE))  # EMPTY
            self.assertEqual(
                self.run_cli(
                    "--repo-root", str(ROOT), "validate", str(path),
                    "--expect", sft.SAVE_COMPAT_EMPTY,
                ),
                0,
            )

    def test_validate_missing_file_is_io_error(self):
        self.assertEqual(
            self.run_cli(
                "--repo-root", str(ROOT), "validate", "/nonexistent/path/save.bin"
            ),
            1,
        )


class CliInspectTests(unittest.TestCase):
    def test_inspect_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.bin"
            header = make_header(valid=True)
            meta = make_meta(format_version=1, compat_epoch=1)
            path.write_bytes(bytes(make_image(header, meta)))
            self.assertEqual(
                sft.main(["--repo-root", str(ROOT), "inspect", str(path)]), 0
            )


class CliMigrateTests(unittest.TestCase):
    def test_successful_v0_to_v1_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "migrated.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)  # v0: no metadata at all
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)

            exit_code = sft.main(
                ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
            )
            self.assertEqual(exit_code, 0)

            # Source must be byte-for-byte untouched.
            self.assertEqual(source.read_bytes(), source_bytes)

            # Destination must classify as CURRENT.
            migrated = dest.read_bytes()
            epoch = sft.resolve_save_compat_epoch(ROOT)
            self.assertEqual(sft.classify_image(migrated, epoch), sft.SAVE_COMPAT_CURRENT)

            # Only the metadata region should differ from the source; the
            # header and every other byte are preserved out-of-place.
            self.assertEqual(
                migrated[: sft.META_OFFSET], source_bytes[: sft.META_OFFSET]
            )
            self.assertEqual(
                migrated[sft.META_OFFSET + sft.META_SIZE :],
                source_bytes[sft.META_OFFSET + sft.META_SIZE :],
            )

    def test_already_current_source_migrates_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "current.bin"
            dest = Path(tmp) / "migrated.bin"
            epoch = sft.resolve_save_compat_epoch(ROOT)
            header = make_header(valid=True)
            meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT, compat_epoch=epoch)
            source.write_bytes(bytes(make_image(header, meta)))

            exit_code = sft.main(
                ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                sft.classify_image(dest.read_bytes(), epoch), sft.SAVE_COMPAT_CURRENT
            )

    def test_failed_migration_preserves_source_and_writes_no_dest(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "corrupt.bin"
            dest = Path(tmp) / "should-not-exist.bin"
            header = make_header(valid=False)  # HEADER_CORRUPT, non-blank
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)

            exit_code = sft.main(
                ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
            )
            self.assertEqual(exit_code, 4)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertFalse(dest.exists())

    def test_migrate_refuses_source_equals_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "same.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            path.write_bytes(bytes(make_image(header, meta)))

            exit_code = sft.main(
                ["--repo-root", str(ROOT), "migrate", str(path), str(path)]
            )
            self.assertEqual(exit_code, 6)

    def test_migrate_refuses_source_equals_destination_via_different_spelling(self):
        """Refusal must be based on resolved path identity, not string
        equality (e.g. a relative vs. absolute spelling of the same file)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "same.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            path.write_bytes(bytes(make_image(header, meta)))

            alt_spelling = Path(tmp) / "." / "same.bin"
            exit_code = sft.main(
                ["--repo-root", str(ROOT), "migrate", str(path), str(alt_spelling)]
            )
            self.assertEqual(exit_code, 6)

    def test_migrate_refuses_hard_linked_destination_alias(self):
        """A hard link to the source is a distinct path but the very same
        file (same device+inode). Path.resolve() alone cannot detect this
        (there is no symlink to follow and the two path strings are
        genuinely different), so it must be caught separately via
        os.path.samefile() identity and refused with the same exit code 6
        as any other source==destination alias -- not treated as an
        ordinary "destination already exists" (exit 7) case."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.bin"
            hardlink_dest = Path(tmp) / "hardlink_alias.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)
            os.link(str(source), str(hardlink_dest))
            self.assertTrue(os.path.samefile(str(source), str(hardlink_dest)))

            exit_code = sft.main(
                [
                    "--repo-root", str(ROOT), "migrate",
                    str(source), str(hardlink_dest),
                ]
            )

            self.assertEqual(exit_code, 6)
            # Both directory entries point at the same inode, so this
            # assertion also proves the source's bytes were left
            # completely untouched (there is only one copy of the data).
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(hardlink_dest.read_bytes(), source_bytes)
            self.assertTrue(self._no_stray_temp_files(source.parent))

    def test_migrate_refuses_hard_linked_destination_alias_even_with_force(self):
        """--force governs overwriting an unrelated existing destination;
        it must never allow a source to be "migrated" onto a hard-linked
        alias of itself."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.bin"
            hardlink_dest = Path(tmp) / "hardlink_alias.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)
            os.link(str(source), str(hardlink_dest))

            exit_code = sft.main(
                [
                    "--repo-root", str(ROOT), "migrate",
                    str(source), str(hardlink_dest), "--force",
                ]
            )

            self.assertEqual(exit_code, 6)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(hardlink_dest.read_bytes(), source_bytes)
            self.assertTrue(self._no_stray_temp_files(source.parent))

    def test_migrate_missing_source_is_io_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "dest.bin"
            exit_code = sft.main(
                [
                    "--repo-root", str(ROOT), "migrate",
                    str(Path(tmp) / "nonexistent.bin"), str(dest),
                ]
            )
            self.assertEqual(exit_code, 1)
            self.assertFalse(dest.exists())

    def _no_stray_temp_files(self, directory: Path) -> bool:
        return not any(directory.glob(".*.tmp"))

    def test_migrate_refuses_existing_destination_without_force(self):
        """The safe default must not silently truncate/overwrite an
        existing destination file."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)
            existing_dest_bytes = b"\x42" * sft.SRAM_SIZE
            dest.write_bytes(existing_dest_bytes)

            exit_code = sft.main(
                ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
            )

            self.assertEqual(exit_code, 7)
            # Neither the source nor the pre-existing destination may be
            # touched by a refused migration.
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(dest.read_bytes(), existing_dest_bytes)
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_force_overwrites_existing_destination(self):
        """--force is the only way to allow overwriting an existing
        destination, and it must still publish a fully valid result."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)
            dest.write_bytes(b"\x42" * sft.SRAM_SIZE)

            exit_code = sft.main(
                ["--repo-root", str(ROOT), "migrate", str(source), str(dest), "--force"]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(source.read_bytes(), source_bytes)
            epoch = sft.resolve_save_compat_epoch(ROOT)
            self.assertEqual(
                sft.classify_image(dest.read_bytes(), epoch), sft.SAVE_COMPAT_CURRENT
            )
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_publish_atomicity_uses_temp_file_and_hard_link(self):
        """The default (no --force) publish must never open the
        destination for writing directly -- only a temp file in its
        directory, published via the OS-enforced fail-if-exists
        os.link(), not os.replace()."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source.write_bytes(bytes(make_image(header, meta)))

            real_link = sft.os.link
            recorded = {}

            def spy_link(src, dst):
                recorded["src"] = Path(src)
                recorded["dst"] = Path(dst)
                # The temp file must live beside dest, never be dest
                # itself, and still exist (not yet linked) at call time.
                self.assertNotEqual(Path(src), dest.resolve())
                self.assertEqual(Path(dst), dest.resolve())
                self.assertTrue(Path(src).exists())
                return real_link(src, dst)

            with mock.patch.object(
                sft.os, "link", side_effect=spy_link
            ) as mocked_link, mock.patch.object(
                sft.os, "replace"
            ) as mocked_replace:
                exit_code = sft.main(
                    ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("src", recorded)
            mocked_link.assert_called_once()
            mocked_replace.assert_not_called()
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_force_publish_uses_os_replace_not_os_link(self):
        """--force must publish via os.replace() (unconditional atomic
        overwrite), never via the default no-clobber os.link() path."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source.write_bytes(bytes(make_image(header, meta)))
            dest.write_bytes(b"\x42" * sft.SRAM_SIZE)

            with mock.patch.object(
                sft.os, "replace", side_effect=sft.os.replace
            ) as mocked_replace, mock.patch.object(
                sft.os, "link"
            ) as mocked_link:
                exit_code = sft.main(
                    [
                        "--repo-root", str(ROOT), "migrate",
                        str(source), str(dest), "--force",
                    ]
                )

            self.assertEqual(exit_code, 0)
            mocked_replace.assert_called_once()
            mocked_link.assert_not_called()
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_destination_created_between_precheck_and_publish_is_not_overwritten(self):
        """Regression test (second review gate, finding #1): the no-force
        default must be atomically no-clobber AT PUBLICATION TIME, not
        merely precheck-only. Simulates a concurrent writer creating the
        destination strictly *after* cmd_migrate's early dest.exists()
        precheck has already observed it as absent (so that precheck
        passes) but before the temp file is actually published --
        os.link()'s OS-enforced EEXIST must still refuse to publish onto,
        and must not disturb, the concurrently-created destination."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)
            # dest does not exist yet -- cmd_migrate's early precheck
            # will pass and proceed to read/classify/build/publish.

            concurrent_dest_bytes = b"\x99" * sft.SRAM_SIZE
            real_link = sft.os.link

            def racy_link(src, dst):
                # Simulate another process winning the race and creating
                # the real destination file strictly between the early
                # precheck (already evaluated as absent) and this
                # publish call, then let the REAL os.link() run so
                # genuine OS fail-if-exists semantics are exercised, not
                # a canned mock exception.
                Path(dst).write_bytes(concurrent_dest_bytes)
                return real_link(src, dst)

            with mock.patch.object(sft.os, "link", side_effect=racy_link):
                exit_code = sft.main(
                    ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
                )

            self.assertEqual(exit_code, 7)
            self.assertEqual(source.read_bytes(), source_bytes)
            # The concurrently-created destination must be preserved
            # exactly -- never overwritten/truncated by the losing
            # migrate attempt.
            self.assertEqual(dest.read_bytes(), concurrent_dest_bytes)
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_simulated_publish_failure_preserves_source_and_leaves_no_partial_dest(self):
        """If the final atomic publish fails (disk full, permissions,
        ...), no destination file may appear and the temp file must be
        cleaned up; the source must remain byte-for-byte untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)

            with mock.patch.object(
                sft.os, "link", side_effect=OSError("simulated publish failure")
            ):
                exit_code = sft.main(
                    ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertFalse(dest.exists())
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_simulated_force_publish_failure_preserves_source_and_leaves_no_partial_dest(self):
        """The --force path (os.replace()) must have the same
        no-partial-destination/source-preservation guarantee on a
        simulated publish failure as the default (os.link()) path."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)
            existing_dest_bytes = b"\x42" * sft.SRAM_SIZE
            dest.write_bytes(existing_dest_bytes)

            with mock.patch.object(
                sft.os, "replace", side_effect=OSError("simulated publish failure")
            ):
                exit_code = sft.main(
                    [
                        "--repo-root", str(ROOT), "migrate",
                        str(source), str(dest), "--force",
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(source.read_bytes(), source_bytes)
            # A failed --force publish must not leave a truncated
            # destination -- the pre-existing (pre-force) content must
            # remain exactly as it was.
            self.assertEqual(dest.read_bytes(), existing_dest_bytes)
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_simulated_write_failure_preserves_source_and_leaves_no_partial_dest(self):
        """If the temp-file write itself fails (e.g. fsync error), no
        destination file may appear, the temp file is cleaned up, and the
        source must remain untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)

            with mock.patch.object(
                sft.os, "fsync", side_effect=OSError("simulated write failure")
            ):
                exit_code = sft.main(
                    ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertFalse(dest.exists())
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_simulated_mkstemp_failure_preserves_source_and_leaves_no_residue(self):
        """Regression test (second review gate, finding #2): if
        tempfile.mkstemp() itself fails (e.g. too many open files, a
        full disk, or an unwritable destination directory), the failure
        must be caught deterministically -- sft.main() must return a
        plain exit code, never let the OSError propagate as an uncaught
        traceback -- with no temp file or destination residue and the
        source left byte-for-byte untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source_bytes = bytes(make_image(header, meta))
            source.write_bytes(source_bytes)

            with mock.patch.object(
                sft.tempfile,
                "mkstemp",
                side_effect=OSError("simulated mkstemp failure"),
            ):
                # If mkstemp's OSError were left uncaught, this call
                # itself would raise instead of returning -- the
                # assertion below on a clean int return is therefore
                # itself proof that no traceback escaped.
                exit_code = sft.main(
                    ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
                )

            self.assertIsInstance(exit_code, int)
            self.assertEqual(exit_code, 1)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertFalse(dest.exists())
            self.assertTrue(self._no_stray_temp_files(dest.parent))

    def test_migrate_dest_in_nonexistent_subdirectory_is_created(self):
        """The atomic publish helper creates the destination's parent
        directory if needed, and still leaves no partial file on
        success."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.bin"
            dest = Path(tmp) / "nested" / "dir" / "dest.bin"
            header = make_header(valid=True)
            meta = make_meta(present=False)
            source.write_bytes(bytes(make_image(header, meta)))

            exit_code = sft.main(
                ["--repo-root", str(ROOT), "migrate", str(source), str(dest)]
            )

            self.assertEqual(exit_code, 0)
            epoch = sft.resolve_save_compat_epoch(ROOT)
            self.assertEqual(
                sft.classify_image(dest.read_bytes(), epoch), sft.SAVE_COMPAT_CURRENT
            )
            self.assertTrue(self._no_stray_temp_files(dest.parent))


class BuildCurrentExpansionSaveMetaTests(unittest.TestCase):
    def test_built_metadata_classifies_current_against_repo_epoch(self):
        meta = sft.build_current_expansion_save_meta(ROOT)
        epoch = sft.resolve_save_compat_epoch(ROOT)
        self.assertEqual(meta.compat_epoch, epoch)
        self.assertEqual(meta.format_version, sft.SAVE_FORMAT_VERSION_CURRENT)
        self.assertEqual(meta.checksum, meta.computed_checksum())

        header = make_header(valid=True)
        image = make_image(header, bytearray(meta.pack()))
        self.assertEqual(sft.classify_image(bytes(image), epoch), sft.SAVE_COMPAT_CURRENT)

    def test_built_metadata_stamps_a_valid_default_user_prefs_record(self):
        """A brand-new save's ExpansionUserPrefs sub-record (issue #18
        sprint 2/6) on THIS repo's real (single-enabled-locale, `en`)
        config.mk must classify VALID -- there is no real first-start
        ambiguity to prompt for on a single-locale build, so auto-
        stamping the configured default now is equivalent to (and
        strictly cheaper than) letting the runtime AUTO_SELECT path do
        the identical write on this save's own first boot."""
        meta = sft.build_current_expansion_save_meta(ROOT)
        locale_count, enabled_mask, default_locale_id = sft.resolve_user_prefs_locale_context(ROOT)
        self.assertLessEqual(bin(enabled_mask).count("1"), 1,
                              "this repo's real config.mk is expected to enable exactly one locale; "
                              "if that ever changes, this test's VALID expectation must move to the "
                              "multi-locale UNSET tests below instead")
        prefs_bytes = meta.reserved[
            sft.EXPANSION_USER_PREFS_META_OFFSET:
            sft.EXPANSION_USER_PREFS_META_OFFSET + sft.EXPANSION_USER_PREFS_SIZE
        ]
        state, prefs = sft.classify_user_prefs_bytes(prefs_bytes, locale_count, enabled_mask)
        self.assertEqual(state, sft.EXPANSION_USER_PREFS_VALID)
        self.assertEqual(prefs.locale_id, default_locale_id)
        self.assertEqual(prefs.flags, 0)  # auto-populated default, not an explicit player choice

        # Every byte past the stamped record is still zeroed headroom.
        headroom = meta.reserved[sft.EXPANSION_USER_PREFS_META_OFFSET + sft.EXPANSION_USER_PREFS_SIZE:]
        self.assertEqual(headroom, b"\x00" * len(headroom))


class BuildDefaultReservedBytesForLocaleContextTests(unittest.TestCase):
    """Issue #18 sprint 6 runtime blocker fix: BuildCurrentExpansionSaveMeta()
    (src/bmsave-lib.c) must only auto-stamp a VALID default
    ExpansionUserPrefs record for a single-enabled-locale build; a
    multi-enabled-locale build's fresh save must leave that record at the
    canonical all-zero EXPANSION_USER_PREFS_UNSET pattern so its
    mandatory first-start prompt is never silently skipped. Exercised
    through the pure, repo_root-independent
    build_default_reserved_bytes_for_locale_context() helper -- no fake
    repository/config.mk needed."""

    LOCALE_COUNT = 8

    def test_single_enabled_locale_stamps_valid(self):
        reserved = sft.build_default_reserved_bytes_for_locale_context(
            self.LOCALE_COUNT, enabled_locale_mask=0x1, default_locale_id=0
        )
        self.assertEqual(len(reserved), sft.EXPANSION_SAVE_META_RESERVED_SIZE)
        prefs_bytes = reserved[:sft.EXPANSION_USER_PREFS_SIZE]
        state, prefs = sft.classify_user_prefs_bytes(prefs_bytes, self.LOCALE_COUNT, 0x1)
        self.assertEqual(state, sft.EXPANSION_USER_PREFS_VALID)
        self.assertEqual(prefs.locale_id, 0)
        self.assertEqual(prefs.flags, 0)
        self.assertEqual(reserved[sft.EXPANSION_USER_PREFS_SIZE:], b"\x00" * (
            sft.EXPANSION_SAVE_META_RESERVED_SIZE - sft.EXPANSION_USER_PREFS_SIZE
        ))

    def test_zero_enabled_locale_defensive_fallback_still_stamps_valid(self):
        """Mirrors ExpansionLanguageMenu_DecideStartupAction()'s own
        documented "enabledLocaleCount == 0 is treated exactly like 1"
        defensive fallback (include/expansion_language_menu.h) -- can
        only arise from a self-contradictory build configuration, never
        a real one, but this popcount-based decision must collapse the
        same way as that runtime one does."""
        reserved = sft.build_default_reserved_bytes_for_locale_context(
            self.LOCALE_COUNT, enabled_locale_mask=0x0, default_locale_id=0
        )
        prefs_bytes = reserved[:sft.EXPANSION_USER_PREFS_SIZE]
        # Classify against mask 0x1 here purely to prove the *stamped*
        # record's own bytes are well-formed/current -- a real
        # enabled_locale_mask=0x0 build is unreachable in practice (see
        # docstring above) and would classify every locale id DISABLED.
        state, prefs = sft.classify_user_prefs_bytes(prefs_bytes, self.LOCALE_COUNT, 0x1)
        self.assertEqual(state, sft.EXPANSION_USER_PREFS_VALID)

    def test_multi_enabled_locale_leaves_reserved_canonically_unset(self):
        reserved = sft.build_default_reserved_bytes_for_locale_context(
            self.LOCALE_COUNT, enabled_locale_mask=0x81, default_locale_id=0  # en (bit 0) + qps-ploc (bit 7)
        )
        self.assertEqual(len(reserved), sft.EXPANSION_SAVE_META_RESERVED_SIZE)
        self.assertEqual(reserved, b"\x00" * sft.EXPANSION_SAVE_META_RESERVED_SIZE)

        prefs_bytes = reserved[:sft.EXPANSION_USER_PREFS_SIZE]
        state, _prefs = sft.classify_user_prefs_bytes(prefs_bytes, self.LOCALE_COUNT, 0x81)
        self.assertEqual(state, sft.EXPANSION_USER_PREFS_UNSET)

    def test_multi_enabled_locale_never_touches_headroom_bytes_differently_than_single(self):
        """Both branches must produce the exact same total reserved-tail
        length -- only the *content*, never the *size*, of the stamped
        region differs by branch."""
        single = sft.build_default_reserved_bytes_for_locale_context(self.LOCALE_COUNT, 0x1, 0)
        multi = sft.build_default_reserved_bytes_for_locale_context(self.LOCALE_COUNT, 0x81, 0)
        self.assertEqual(len(single), len(multi))


# --- ExpansionUserPrefs (issue #18 sprint 2) --------------------------------


class ExpansionUserPrefsPackTests(unittest.TestCase):
    """Round-trip pack/unpack/checksum coverage, mirroring
    Checksum16Tests/IsRegionBlankTests' style above for the outer
    ExpansionSaveMeta record."""

    def test_pack_unpack_round_trip(self):
        prefs = sft.build_default_user_prefs(3, explicit_selection=True)
        raw = prefs.pack()
        self.assertEqual(len(raw), sft.EXPANSION_USER_PREFS_SIZE)
        round_tripped = sft.ExpansionUserPrefs.unpack(raw)
        self.assertEqual(round_tripped, prefs)

    def test_build_default_checksum_matches_computed_checksum(self):
        prefs = sft.build_default_user_prefs(0, explicit_selection=False)
        self.assertEqual(prefs.checksum, prefs.computed_checksum())

    def test_explicit_selection_sets_flag_bit(self):
        explicit = sft.build_default_user_prefs(0, explicit_selection=True)
        implicit = sft.build_default_user_prefs(0, explicit_selection=False)
        self.assertEqual(explicit.flags, sft.EXPANSION_USER_PREFS_FLAG_LOCALE_EXPLICIT)
        self.assertEqual(implicit.flags, 0)


class ExpansionUserPrefsClassifyMatrixTests(unittest.TestCase):
    """Byte-exact coverage of every EXPANSION_USER_PREFS_* state and its
    ExpansionUserPrefs_Normalize() fallback -- the same matrix exercised
    natively (real C) in test_expansion_user_prefs_native.py; this class
    proves the Python mirror's *own* internal consistency/precedence
    independent of that native cross-check, plus a couple of pure-Python-
    only edge cases (empty-region vacuous case, explicit blank-vs-zero
    distinction) that file doesn't need to duplicate."""

    LOCALE_COUNT = 8
    ENABLED_MASK = 0x1  # only locale 0 ("en") enabled
    DEFAULT_LOCALE_ID = 0

    def classify(self, prefs: "sft.ExpansionUserPrefs", region_unset: bool) -> str:
        return sft.classify_user_prefs_raw(prefs, region_unset, self.LOCALE_COUNT, self.ENABLED_MASK)

    def test_all_zero_region_is_unset(self):
        prefs = sft.ExpansionUserPrefs.unpack(bytes(sft.EXPANSION_USER_PREFS_SIZE))
        self.assertEqual(self.classify(prefs, True), sft.EXPANSION_USER_PREFS_UNSET)

    def test_all_0xff_region_is_unset(self):
        prefs = sft.ExpansionUserPrefs.unpack(bytes([0xFF] * sft.EXPANSION_USER_PREFS_SIZE))
        self.assertEqual(self.classify(prefs, True), sft.EXPANSION_USER_PREFS_UNSET)

    def test_valid_current_enabled_locale_is_valid(self):
        prefs = sft.build_default_user_prefs(0)
        self.assertEqual(self.classify(prefs, False), sft.EXPANSION_USER_PREFS_VALID)

    def test_bad_magic_is_corrupt(self):
        prefs = sft.build_default_user_prefs(0)
        prefs.magic = 0x00
        self.assertEqual(self.classify(prefs, False), sft.EXPANSION_USER_PREFS_CORRUPT)

    def test_bad_checksum_is_corrupt(self):
        prefs = sft.build_default_user_prefs(0)
        prefs.checksum ^= 0xFFFF
        self.assertEqual(self.classify(prefs, False), sft.EXPANSION_USER_PREFS_CORRUPT)

    def test_newer_version_is_corrupt(self):
        prefs = sft.build_default_user_prefs(0)
        prefs.version = sft.EXPANSION_USER_PREFS_VERSION_CURRENT + 1
        prefs.checksum = prefs.computed_checksum()
        self.assertEqual(self.classify(prefs, False), sft.EXPANSION_USER_PREFS_CORRUPT)

    def test_unknown_locale_id(self):
        prefs = sft.build_default_user_prefs(self.LOCALE_COUNT + 5)
        self.assertEqual(self.classify(prefs, False), sft.EXPANSION_USER_PREFS_UNKNOWN_LOCALE)

    def test_supported_but_disabled_locale_id(self):
        prefs = sft.build_default_user_prefs(1)  # supported (< LOCALE_COUNT), not in ENABLED_MASK
        self.assertEqual(self.classify(prefs, False), sft.EXPANSION_USER_PREFS_DISABLED_LOCALE)

    def test_older_version_enabled_locale_is_migrated(self):
        prefs = sft.build_default_user_prefs(0)
        prefs.version = 0
        prefs.checksum = prefs.computed_checksum()
        self.assertEqual(self.classify(prefs, False), sft.EXPANSION_USER_PREFS_MIGRATED)

    def test_normalize_valid_and_migrated_trust_stored_locale(self):
        for version, expected_state in (
            (sft.EXPANSION_USER_PREFS_VERSION_CURRENT, sft.EXPANSION_USER_PREFS_VALID),
            (0, sft.EXPANSION_USER_PREFS_MIGRATED),
        ):
            with self.subTest(version=version):
                prefs = sft.build_default_user_prefs(0)
                prefs.version = version
                prefs.checksum = prefs.computed_checksum()
                state = self.classify(prefs, False)
                self.assertEqual(state, expected_state)
                locale_id, requires_prompt = sft.normalize_user_prefs(prefs, state, self.DEFAULT_LOCALE_ID)
                self.assertEqual(locale_id, 0)
                self.assertFalse(requires_prompt)

    def test_normalize_every_other_state_falls_back_to_default_and_requires_prompt(self):
        unknown_prefs = sft.build_default_user_prefs(self.LOCALE_COUNT + 5)
        state = self.classify(unknown_prefs, False)
        locale_id, requires_prompt = sft.normalize_user_prefs(unknown_prefs, state, self.DEFAULT_LOCALE_ID)
        self.assertEqual(state, sft.EXPANSION_USER_PREFS_UNKNOWN_LOCALE)
        self.assertEqual(locale_id, self.DEFAULT_LOCALE_ID)
        self.assertTrue(requires_prompt)


class MigratePreservesUserPrefsTests(unittest.TestCase):
    """Issue #18 sprint 2's no-wipe migration contract: cmd_migrate must
    carry a source's existing ExpansionUserPrefs record (inside
    `reserved`) forward verbatim, never silently replace it with a fresh
    default -- and must now also accept a MIGRATABLE_OLDER source (a real
    formatVersion bump exists to exercise since this sprint), not only
    the v0/already-current sources slice 1 originally supported."""

    def _migrate(self, source_bytes: bytes):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.bin"
            dest = Path(tmp) / "dest.bin"
            source.write_bytes(source_bytes)
            exit_code = sft.main(["--repo-root", str(ROOT), "migrate", str(source), str(dest)])
            return exit_code, source.read_bytes(), (dest.read_bytes() if dest.exists() else None)

    def test_migrate_preserves_real_stored_prefs_from_a_current_source(self):
        epoch = sft.resolve_save_compat_epoch(ROOT)
        header = make_header(valid=True)

        custom_prefs = sft.build_default_user_prefs(0, explicit_selection=True)
        prefs_bytes = custom_prefs.pack()
        reserved = prefs_bytes + b"\x00" * (sft.META_SIZE - sft.META_CHECKSUM_DOMAIN - 2 - len(prefs_bytes))
        meta = sft.ExpansionSaveMeta(
            magic=sft.META_MAGIC,
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT,
            compat_epoch=epoch,
            abi_id=sft.SAVE_ABI_ID_AAPCS,
            framework_version_packed=0x000100,
            config_fingerprint=b"deadbeefcafebabe\x00",
            build_commit_short=b"cafef00d\x00",
            checksum=0,
            reserved=reserved,
        )
        meta.checksum = meta.computed_checksum()
        source_bytes = bytes(make_image(header, bytearray(meta.pack())))

        exit_code, source_after, dest_bytes = self._migrate(source_bytes)
        self.assertEqual(exit_code, 0)
        self.assertEqual(source_after, source_bytes)  # source untouched

        dest_meta = sft.ExpansionSaveMeta.unpack(
            dest_bytes[sft.META_OFFSET:sft.META_OFFSET + sft.META_SIZE]
        )
        locale_count, enabled_mask, _default = sft.resolve_user_prefs_locale_context(ROOT)
        state, dest_prefs = sft.classify_user_prefs_bytes(
            dest_meta.reserved[:sft.EXPANSION_USER_PREFS_SIZE], locale_count, enabled_mask
        )
        self.assertEqual(dest_prefs.locale_id, 0)
        self.assertEqual(dest_prefs.flags, sft.EXPANSION_USER_PREFS_FLAG_LOCALE_EXPLICIT)
        self.assertEqual(state, sft.EXPANSION_USER_PREFS_VALID)

        # Migration only ever refreshed formatVersion/compatEpoch/
        # diagnostics/checksum -- the reserved tail (prefs record
        # included) is carried forward byte-for-byte.
        self.assertEqual(dest_meta.reserved, meta.reserved)

    def test_migratable_older_source_is_now_accepted(self):
        """A real formatVersion bump now exists (issue #18 sprint 2), so
        an older-but-supported source must migrate successfully -- not
        just the v0/no-metadata-at-all and already-current cases slice 1
        originally supported."""
        header = make_header(valid=True)
        meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT - 1, compat_epoch=1)
        source_bytes = bytes(make_image(header, meta))

        exit_code, source_after, dest_bytes = self._migrate(source_bytes)
        self.assertEqual(exit_code, 0)
        self.assertEqual(source_after, source_bytes)
        epoch = sft.resolve_save_compat_epoch(ROOT)
        self.assertEqual(sft.classify_image(dest_bytes, epoch), sft.SAVE_COMPAT_CURRENT)

    def test_migrate_from_v0_legacy_source_gets_fresh_default_prefs(self):
        """A SAVE_COMPAT_VALID_LEGACY_OR_VANILLA source has no prior
        ExpansionSaveMeta.reserved at all to preserve, so it must get a
        fresh, valid default ExpansionUserPrefs record -- never an
        UNSET/blank one carried forward from a region that was never a
        real ExpansionSaveMeta to begin with."""
        header = make_header(valid=True)
        meta = make_meta(present=False)  # v0: no metadata at all
        source_bytes = bytes(make_image(header, meta))

        exit_code, source_after, dest_bytes = self._migrate(source_bytes)
        self.assertEqual(exit_code, 0)
        self.assertEqual(source_after, source_bytes)

        dest_meta = sft.ExpansionSaveMeta.unpack(
            dest_bytes[sft.META_OFFSET:sft.META_OFFSET + sft.META_SIZE]
        )
        locale_count, enabled_mask, default_locale_id = sft.resolve_user_prefs_locale_context(ROOT)
        state, dest_prefs = sft.classify_user_prefs_bytes(
            dest_meta.reserved[:sft.EXPANSION_USER_PREFS_SIZE], locale_count, enabled_mask
        )
        self.assertEqual(state, sft.EXPANSION_USER_PREFS_VALID)
        self.assertEqual(dest_prefs.locale_id, default_locale_id)


if __name__ == "__main__":
    unittest.main()
