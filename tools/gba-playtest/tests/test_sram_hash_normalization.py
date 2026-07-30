"""Host-only coverage for the SRAM-hash normalization mechanism added to
fix the `expansion-modern-savefmt-check` instability introduced by
`fe26c181` (see docs/save_format.md's "SRAM hash policy: exact vs.
normalized").

Root cause recap: `struct ExpansionSaveMeta`'s `buildCommitShort` field
(and, transitively, its `checksum` field, whose domain covers
`buildCommitShort`) is intentionally diagnostic build metadata that
differs on every commit. A committed whole-0x8000-byte SRAM fingerprint
for any `SAVE_COMPAT_CURRENT`-classified checkpoint therefore breaks on
every legitimate follow-up commit. `sram_hash_exclude_ranges` lets a
scenario checkpoint opt into a "normalized" hash that skips exactly those
two byte ranges (and nothing else), while checkpoints that omit the field
keep the original exact whole-image hash unchanged.

None of these tests require libmGBA or a built ROM: they exercise the
same FNV-1a construction end-to-end via `sram_hash_mirror.py` (a byte-
exact host mirror of backend.c's hash_sram()/offset_excluded()) against
synthetic SRAM images built with scripts/modernize/tests'
`test_save_format_tool.make_meta/make_header/make_image` helpers -- the
same fixture builders `sram_fixture.py`'s runtime fixtures are built
from. `save_format_tool.classify_image()` (the real, unmodified
classifier) is used throughout to prove classification and checksum
validity are unaffected by hash normalization.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
SCENARIOS_DIR = PLAYTEST_DIR / "scenarios"
MODERNIZE_DIR = REPO_ROOT / "scripts" / "modernize"
MODERNIZE_TESTS_DIR = MODERNIZE_DIR / "tests"

for _extra_path in (
    str(PLAYTEST_DIR),
    str(PLAYTEST_DIR / "tests"),
    str(MODERNIZE_DIR),
    str(MODERNIZE_TESTS_DIR),
):
    if _extra_path not in sys.path:
        sys.path.insert(0, _extra_path)

import gba_playtest  # noqa: E402
import save_format_tool as sft  # noqa: E402
import sram_fixture as sf  # noqa: E402
from sram_hash_mirror import compute_sram_hash  # noqa: E402
from test_save_format_tool import make_header, make_image, make_meta  # noqa: E402

# The exact byte ranges committed in scenarios/savecompat-current.json and
# scenarios/savecompat-erase.json: (configFingerprint, 17 bytes),
# (buildCommitShort, 9 bytes) and (checksum, 2 bytes), all meta-relative
# offsets translated to absolute SRAM offsets via sft.META_OFFSET.
# Re-derived from save_format_tool.py's own constants here (rather than
# hardcoded a second time) so this test fails loudly if the struct layout
# ever moves. configFingerprint was added to the exclusion set in the
# issue #6 sprint-1 gate remediation: it is a purely diagnostic field
# (config feature flags change behaviour/identity but NOT save
# layout/epoch), and it is preset-derived (debug vs release fingerprints
# differ), so a build-to-build config-schema change would otherwise drift
# the "same persisted save" normalized hash -- exactly the drift this
# remediation removes. Ordered ascending and non-overlapping, matching the
# scenario/backend requirement.
CONFIG_FINGERPRINT_META_OFFSET = 0x10  # magic(4)+ver(1)+pad(1)+epoch(2)+abi(1)+pad(3)+fwver(4) -> cfgfp
CONFIG_FINGERPRINT_LENGTH = 17          # 16 hex chars + NUL
BUILD_COMMIT_META_OFFSET = 0x24  # ... +cfgfp(17)+pad(3) -> buildCommitShort
BUILD_COMMIT_LENGTH = 9
CHECKSUM_META_OFFSET = 0x2E
CHECKSUM_LENGTH = 2

EXCLUDE_RANGES = (
    (sft.META_OFFSET + CONFIG_FINGERPRINT_META_OFFSET, CONFIG_FINGERPRINT_LENGTH),
    (sft.META_OFFSET + BUILD_COMMIT_META_OFFSET, BUILD_COMMIT_LENGTH),
    (sft.META_OFFSET + CHECKSUM_META_OFFSET, CHECKSUM_LENGTH),
)


def _current_image(build_commit_short: bytes, config_fingerprint: bytes = b"deadbeefcafebabe\x00") -> bytes:
    """Builds a SAVE_COMPAT_CURRENT-classified SRAM image with a chosen
    (synthetic) build_commit_short/config_fingerprint and a validly
    recomputed checksum -- simulating "the same build, a different
    commit/build-id" without needing an actual second git commit."""
    epoch = sf.resolve_epoch(REPO_ROOT)
    header = make_header(valid=True)
    meta = make_meta(
        compat_epoch=epoch,
        config_fingerprint=config_fingerprint,
        build_commit_short=build_commit_short,
    )
    image = bytes(make_image(header, meta))
    assert sft.classify_image(image, epoch) == sf.STATE_CURRENT
    return image


class BuildCommitDiagnosticStabilityTests(unittest.TestCase):
    """Requirement 7, bullet 1: two metadata records differing only in
    build-commit diagnostic fields (each with a validly recomputed
    checksum) must yield the same stable/normalized hash."""

    def test_build_commit_only_difference_yields_same_normalized_hash(self):
        image_a = _current_image(b"cafef00d\x00")
        image_b = _current_image(b"deadbeef\x00")

        normalized_a = compute_sram_hash(image_a, EXCLUDE_RANGES)
        normalized_b = compute_sram_hash(image_b, EXCLUDE_RANGES)
        self.assertEqual(
            normalized_a,
            normalized_b,
            "normalized hash must be invariant to build_commit_short/checksum",
        )

    def test_build_commit_only_difference_changes_exact_hash(self):
        # Sanity check proving the two fixtures really do differ in raw
        # bytes -- otherwise the previous test would be vacuous.
        image_a = _current_image(b"cafef00d\x00")
        image_b = _current_image(b"deadbeef\x00")

        exact_a = compute_sram_hash(image_a, ())
        exact_b = compute_sram_hash(image_b, ())
        self.assertNotEqual(
            exact_a,
            exact_b,
            "fixtures must actually differ, or the normalization test above is vacuous",
        )

    def test_config_fingerprint_difference_is_excluded(self):
        # Issue #6 sprint-1 gate remediation (INVERTS the prior
        # "..._is_not_excluded" assertion): config_fingerprint IS now in
        # EXCLUDE_RANGES. The earlier code assumed it "does not vary per
        # commit"; that was wrong -- it is preset/config-schema derived
        # (scripts/modernize/expansion_config.py's fingerprint_fields()),
        # so adding a config feature flag (even one defaulting to OFF, as
        # issue #6 did) changes it and drifted the normalized "same
        # persisted save" hash. Two images differing ONLY in
        # config_fingerprint must now normalize to the SAME hash -- that is
        # the whole point of excluding this diagnostic field.
        image_a = _current_image(b"cafef00d\x00", config_fingerprint=b"deadbeefcafebabe\x00")
        image_b = _current_image(b"cafef00d\x00", config_fingerprint=b"0000000000000000\x00")

        self.assertEqual(
            compute_sram_hash(image_a, EXCLUDE_RANGES),
            compute_sram_hash(image_b, EXCLUDE_RANGES),
            "normalized hash must be invariant to the diagnostic config_fingerprint",
        )
        # Sanity: they really do differ in raw bytes (otherwise vacuous),
        # so the exact whole-image hash still separates them.
        self.assertNotEqual(
            compute_sram_hash(image_a, ()),
            compute_sram_hash(image_b, ()),
            "fixtures must actually differ, or the normalization test is vacuous",
        )
        # Classification is unaffected either way -- config_fingerprint is
        # diagnostic-only and never gates compatibility.
        epoch = sf.resolve_epoch(REPO_ROOT)
        self.assertEqual(sft.classify_image(image_a, epoch), sf.STATE_CURRENT)
        self.assertEqual(sft.classify_image(image_b, epoch), sf.STATE_CURRENT)


class ChecksumAndCompatibilityFieldIntegrityTests(unittest.TestCase):
    """Requirement 7, bullet 2 / requirement 4: corruption of stable
    compatibility fields, or of the metadata checksum itself, must still
    be detected -- normalizing the hash must not silently disable
    checksum/classification validation."""

    def test_checksum_corruption_is_detected_by_classification(self):
        # The checksum field is inside EXCLUDE_RANGES (so the *hash*
        # can't see corruption there by design), but classify_image()
        # -- which recomputes and compares the checksum independently --
        # must still catch it.
        epoch = sf.resolve_epoch(REPO_ROOT)
        header = make_header(valid=True)
        good_meta = make_meta(compat_epoch=epoch)
        corrupt_meta = make_meta(compat_epoch=epoch, corrupt_checksum=True)

        good_image = bytes(make_image(header, good_meta))
        corrupt_image = bytes(make_image(header, corrupt_meta))

        self.assertEqual(sft.classify_image(good_image, epoch), sf.STATE_CURRENT)
        self.assertEqual(
            sft.classify_image(corrupt_image, epoch),
            sf.STATE_METADATA_CORRUPT,
            "a corrupted metadata checksum must still be rejected, even though "
            "the checksum bytes are excluded from the stable hash",
        )
        # And the normalized hash *does* still differ (checksum corruption
        # changes only the excluded checksum bytes here, since build_commit
        # is held constant -- so this documents, rather than asserts on,
        # the expected/allowed blind spot: hash-based detection of pure
        # checksum-domain corruption is not required, since
        # classify_image() already owns that job explicitly).

    def test_compatibility_field_corruption_changes_normalized_hash(self):
        # format_version/compat_epoch are NOT excluded -- corrupting them
        # must still change the normalized hash (in addition to changing
        # classification), proving the exclusion is narrowly scoped to
        # only the three genuinely build/diagnostic-variable fields
        # (configFingerprint, buildCommitShort, checksum) and no further.
        epoch = sf.resolve_epoch(REPO_ROOT)
        header = make_header(valid=True)
        current_meta = make_meta(compat_epoch=epoch)
        older_meta = make_meta(
            compat_epoch=epoch,
            format_version=(
                sft.SAVE_FORMAT_VERSION_CURRENT - 1 if sft.SAVE_FORMAT_VERSION_CURRENT > 0 else 0
            ),
        )
        current_image = bytes(make_image(header, current_meta))
        older_image = bytes(make_image(header, older_meta))

        self.assertNotEqual(
            compute_sram_hash(current_image, EXCLUDE_RANGES),
            compute_sram_hash(older_image, EXCLUDE_RANGES),
            "corrupting format_version must still change the normalized hash",
        )
        self.assertEqual(sft.classify_image(current_image, epoch), sf.STATE_CURRENT)
        self.assertEqual(sft.classify_image(older_image, epoch), sf.STATE_OLDER)

    def test_metadata_magic_and_save_payload_changes_change_normalized_hash(self):
        # Issue #6 remediation coverage: excluding configFingerprint must
        # not weaken the hash's sensitivity to anything else. A change to
        # the metadata magic (offset META_OFFSET, NOT excluded) or to an
        # ordinary save-payload byte well outside the metadata record must
        # still change the normalized hash -- the exclusion is the 46-byte
        # ExpansionSaveMeta diagnostic window only, never the save payload.
        epoch = sf.resolve_epoch(REPO_ROOT)
        base = bytearray(_current_image(b"cafef00d\x00"))
        base_hash = compute_sram_hash(bytes(base), EXCLUDE_RANGES)

        # (a) flip a metadata magic byte (meta offset 0x00 -> absolute
        # META_OFFSET), which is outside every exclude range.
        magic_mutated = bytearray(base)
        magic_mutated[sft.META_OFFSET] ^= 0xFF
        self.assertNotEqual(
            compute_sram_hash(bytes(magic_mutated), EXCLUDE_RANGES),
            base_hash,
            "metadata magic is not excluded -- corrupting it must change the hash",
        )

        # (b) flip an ordinary save-payload byte far from the metadata
        # record (offset 0x100 is in the global save header/payload region).
        payload_mutated = bytearray(base)
        payload_mutated[0x100] ^= 0xFF
        self.assertNotEqual(
            compute_sram_hash(bytes(payload_mutated), EXCLUDE_RANGES),
            base_hash,
            "an actual save-payload byte change must still change the normalized hash",
        )


class BackScenarioExactHashTests(unittest.TestCase):
    """Requirement 7, bullet 3: non-destructive Back scenarios must keep
    using the exact whole-SRAM hash (no exclude ranges at all)."""

    def test_dialog_back_scenario_declares_no_exclude_ranges(self):
        scenario = gba_playtest.load_scenario(SCENARIOS_DIR / "savecompat-dialog-back.json")
        self.assertTrue(scenario.checkpoints, "expected at least one checkpoint")
        for checkpoint in scenario.checkpoints:
            with self.subTest(checkpoint=checkpoint.name):
                self.assertEqual(
                    checkpoint.sram_hash_exclude_ranges,
                    (),
                    "Back scenario checkpoints must keep the exact whole-image hash",
                )

    def test_back_fixture_is_sensitive_to_every_byte(self):
        # Direct proof that the exact-hash path (no exclude ranges) is
        # still fully sensitive to single-byte differences anywhere in
        # the image -- i.e. normalization did not leak into the exact path.
        image = bytearray(sf.build_fixture_image(sf.STATE_VALID_LEGACY))
        exact_before = compute_sram_hash(bytes(image), ())
        image[0] ^= 0xFF
        exact_after = compute_sram_hash(bytes(image), ())
        self.assertNotEqual(exact_before, exact_after)


class ErasePersistedChangeTests(unittest.TestCase):
    """Requirement 7, bullet 4: erase must prove the image actually
    changed, then classify CURRENT, without depending on a
    commit-specific full-image hash."""

    def test_erase_changes_image_then_classifies_current_regardless_of_commit(self):
        epoch = sf.resolve_epoch(REPO_ROOT)
        before_image = sf.build_fixture_image(sf.STATE_HEADER_CORRUPT)
        after_image_commit_a = _current_image(b"cafef00d\x00")
        after_image_commit_b = _current_image(b"deadbeef\x00")

        # The image actually changed (erase had an effect).
        self.assertNotEqual(
            compute_sram_hash(before_image, EXCLUDE_RANGES),
            compute_sram_hash(after_image_commit_a, EXCLUDE_RANGES),
        )
        # Both post-erase images classify CURRENT ...
        self.assertEqual(sft.classify_image(after_image_commit_a, epoch), sf.STATE_CURRENT)
        self.assertEqual(sft.classify_image(after_image_commit_b, epoch), sf.STATE_CURRENT)
        # ... and the *normalized* fingerprint used to prove that does not
        # depend on which commit produced the erase -- no full-hash
        # dependency on build_commit_short remains.
        self.assertEqual(
            compute_sram_hash(after_image_commit_a, EXCLUDE_RANGES),
            compute_sram_hash(after_image_commit_b, EXCLUDE_RANGES),
        )


class FingerprintRegenerationNotRequiredTests(unittest.TestCase):
    """Requirement 7, bullet 5: fingerprint files must not need
    regeneration for a build-ID-only commit change."""

    def test_committed_current_scenario_hash_stable_across_simulated_commits(self):
        scenario = gba_playtest.load_scenario(SCENARIOS_DIR / "savecompat-current.json")
        self.assertEqual(len(scenario.checkpoints), 1)
        checkpoint = scenario.checkpoints[0]
        self.assertTrue(
            checkpoint.sram_hash_exclude_ranges,
            "savecompat-current.json's checkpoint must declare exclude ranges",
        )
        # The ranges declared in the committed scenario file must be
        # exactly the ones this test derives from save_format_tool.py's
        # own struct-layout constants -- this is what prevents future
        # struct-layout drift from silently invalidating the exclusion.
        self.assertEqual(checkpoint.sram_hash_exclude_ranges, EXCLUDE_RANGES)

        image_commit_a = _current_image(b"cafef00d\x00")
        image_commit_b = _current_image(b"11111111\x00")
        hash_a = compute_sram_hash(image_commit_a, checkpoint.sram_hash_exclude_ranges)
        hash_b = compute_sram_hash(image_commit_b, checkpoint.sram_hash_exclude_ranges)
        self.assertEqual(
            hash_a,
            hash_b,
            "a build-ID-only commit change must not require refreshing "
            "fingerprints/savecompat-current-*.json",
        )

    def test_erase_scenario_checkpoints_all_declare_the_same_exclude_ranges(self):
        scenario = gba_playtest.load_scenario(SCENARIOS_DIR / "savecompat-erase.json")
        current_checkpoints = [
            checkpoint for checkpoint in scenario.checkpoints if checkpoint.sram_hash
        ]
        self.assertTrue(current_checkpoints)
        for checkpoint in current_checkpoints:
            with self.subTest(checkpoint=checkpoint.name):
                self.assertEqual(checkpoint.sram_hash_exclude_ranges, EXCLUDE_RANGES)


if __name__ == "__main__":
    unittest.main()
