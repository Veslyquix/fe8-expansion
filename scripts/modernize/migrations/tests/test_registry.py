"""Tests for scripts/modernize/migrations/registry.py (issue #9).

All fixtures are synthetic in-memory byte arrays -- no committed binary
blobs, ROM dumps, or real user saves -- matching
scripts/modernize/tests/test_save_format_tool.py's own guardrail.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))

import save_format_tool as sft  # noqa: E402

from scripts.modernize.migrations import registry as reg  # noqa: E402


def make_header(valid: bool = True) -> bytearray:
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


def make_meta_absent() -> bytearray:
    return bytearray([0xFF] * sft.META_SIZE)


def make_image(header: bytes, meta: bytes) -> bytearray:
    image = bytearray(b"\x00" * sft.SRAM_SIZE)
    image[sft.HEADER_OFFSET : sft.HEADER_OFFSET + sft.HEADER_SIZE] = header
    image[sft.META_OFFSET : sft.META_OFFSET + sft.META_SIZE] = meta
    return image


def legacy_image() -> bytes:
    """A 'v0' image: valid header, no ExpansionSaveMeta record at all."""
    return bytes(make_image(make_header(valid=True), make_meta_absent()))


def current_image() -> bytes:
    """A real 'current' (today: epoch 2) image, built the same way
    scripts/modernize/save_format_tool.py's own tests build one."""
    meta = sft.build_current_expansion_save_meta(ROOT)
    return bytes(make_image(make_header(valid=True), meta.pack()))


def older_migratable_image() -> bytes:
    """A real 'migratable older' image: valid header, an ExpansionSaveMeta
    record whose formatVersion is one behind sft.SAVE_FORMAT_VERSION_CURRENT
    -- classifies SAVE_COMPAT_MIGRATABLE_OLDER, mirroring a real save
    written before the formatVersion/EXPANSION_SAVE_COMPAT_EPOCH 1 -> 2
    bump this module's `reg.find_step(1, 2)` entry migrates forward from
    (issue #9 release-branch/origin-master merge; issue #18 sprint 2 is
    the actual bump's own origin -- see docs/save_format.md/
    docs/migration_registry.md). Same hand-built-then-checksummed idiom
    scripts/modernize/tests/test_save_format_tool.py's own
    `test_older_format_version_is_migratable_older` fixture uses."""
    meta = sft.ExpansionSaveMeta(
        magic=sft.META_MAGIC,
        format_version=sft.SAVE_FORMAT_VERSION_CURRENT - 1,
        compat_epoch=1,
        abi_id=sft.SAVE_ABI_ID_AAPCS,
        framework_version_packed=0x000100,
        config_fingerprint=b"deadbeefcafebabe\x00",
        build_commit_short=b"cafef00d\x00",
        checksum=0,
        reserved=b"\x00" * (sft.META_SIZE - sft.META_CHECKSUM_DOMAIN - 2),
    )
    meta.checksum = meta.computed_checksum()
    return bytes(make_image(make_header(valid=True), meta.pack()))


def forged_exact_epoch_image(format_version: int) -> bytes:
    """A real, checksum-valid ExpansionSaveMeta record whose raw
    `format_version` is *exactly* `format_version` -- distinct from
    `older_migratable_image()` (always hardcoded to
    `SAVE_FORMAT_VERSION_CURRENT - 1`, i.e. today's real epoch 1): this
    lets a test independently prove that a *different* real epoch that
    still happens to fall into the same broad `SAVE_COMPAT_MIGRATABLE_
    OLDER` bucket (any raw formatVersion below today's live
    `SAVE_FORMAT_VERSION_CURRENT`) is nonetheless correctly told apart
    from the registry's own declared, numbered `epoch_from` -- see
    `ExactSourceEpochEnforcementTests` below (issue #9 residual-
    hardening, finding C: 'a broad classification like
    SAVE_COMPAT_MIGRATABLE_OLDER can include multiple epochs')."""
    meta = sft.ExpansionSaveMeta(
        magic=sft.META_MAGIC,
        format_version=format_version,
        compat_epoch=1,
        abi_id=sft.SAVE_ABI_ID_AAPCS,
        framework_version_packed=0x000100,
        config_fingerprint=b"deadbeefcafebabe\x00",
        build_commit_short=b"cafef00d\x00",
        checksum=0,
        reserved=b"\x00" * (sft.META_SIZE - sft.META_CHECKSUM_DOMAIN - 2),
    )
    meta.checksum = meta.computed_checksum()
    return bytes(make_image(make_header(valid=True), meta.pack()))


def forged_exact_pair_image(format_version: int, compat_epoch: int) -> bytes:
    """Like `forged_exact_epoch_image()` above, but lets a test control
    *both* the raw `format_version` and the raw `compat_epoch` fields of a
    real, checksum-valid ExpansionSaveMeta record independently. Used to
    reproduce the finding-D bypass shape this hardening closes: a
    checksum-valid source whose raw `format_version` genuinely matches a
    declared step's `epoch_from` (so the format-only check alone would
    have accepted it) but whose raw `compat_epoch` is an arbitrary wrong
    value -- e.g. `format_version=1, compat_epoch=999` -- must still be
    rejected before any mutation, because `classify_save_compat_raw()`
    itself never inspects `compat_epoch` at all once `format_version` has
    already resolved the state to `SAVE_COMPAT_MIGRATABLE_OLDER`."""
    meta = sft.ExpansionSaveMeta(
        magic=sft.META_MAGIC,
        format_version=format_version,
        compat_epoch=compat_epoch,
        abi_id=sft.SAVE_ABI_ID_AAPCS,
        framework_version_packed=0x000100,
        config_fingerprint=b"deadbeefcafebabe\x00",
        build_commit_short=b"cafef00d\x00",
        checksum=0,
        reserved=b"\x00" * (sft.META_SIZE - sft.META_CHECKSUM_DOMAIN - 2),
    )
    meta.checksum = meta.computed_checksum()
    return bytes(make_image(make_header(valid=True), meta.pack()))


def make_step(
    epoch_from=1,
    epoch_to=2,
    compat_epoch_from=1,
    compat_epoch_to=2,
    kind=reg.MECHANICAL,
    description="test step",
    manual_steps=(),
):
    """Convenience constructor for a standalone (not REGISTRY-registered)
    MigrationStep in tests that only care about kind/description/manual-
    step validation, not this registry's own real declared transitions --
    defaults to a plausible, self-consistent 1/1 -> 2/2 pair so tests that
    do not care about the exact numbers do not have to repeat all four."""
    return reg.MigrationStep(
        epoch_from=epoch_from,
        epoch_to=epoch_to,
        compat_epoch_from=compat_epoch_from,
        compat_epoch_to=compat_epoch_to,
        kind=kind,
        description=description,
        manual_steps=manual_steps,
    )


class RegistryStructureTests(unittest.TestCase):
    def test_registry_has_v0_to_1_mechanical_entry(self):
        step = reg.find_step(None, 1)
        self.assertIsNotNone(step)
        self.assertEqual(step.kind, reg.MECHANICAL)

    def test_registry_has_1_to_2_mechanical_entry(self):
        """issue #9 release-branch/origin-master merge: origin/master's
        issue #18 sprint 2 bumped EXPANSION_SAVE_COMPAT_EPOCH 1 -> 2; this
        registry must declare the corresponding transition (see
        check_migration_epoch_reachability() in
        scripts/release_rehearsal/consistency.py, which fails the whole
        release manifest until this entry exists)."""
        step = reg.find_step(1, 2)
        self.assertIsNotNone(step)
        self.assertEqual(step.kind, reg.MECHANICAL)

    def test_manual_step_requires_steps(self):
        with self.assertRaises(ValueError):
            make_step(kind=reg.MANUAL, description="x")

    def test_mechanical_step_forbids_manual_steps(self):
        with self.assertRaises(ValueError):
            make_step(kind=reg.MECHANICAL, description="x", manual_steps=("do something",))

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            make_step(kind="bogus", description="x")

    def test_legacy_source_requires_both_fields_absent_together(self):
        """The explicit legacy/absent sentinel is one unambiguous state:
        epoch_from and compat_epoch_from must both be None together, or
        both be real numbered values -- never guessed field-by-field."""
        with self.assertRaises(ValueError):
            make_step(epoch_from=None, compat_epoch_from=1, description="x")
        with self.assertRaises(ValueError):
            make_step(epoch_from=1, compat_epoch_from=None, description="x")

    def test_compat_epoch_ordering_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            make_step(compat_epoch_from=2, compat_epoch_to=1, description="x")

    def test_find_step_missing_returns_none(self):
        self.assertIsNone(reg.find_step(5, 6))


class CheckRegistryTests(unittest.TestCase):
    def test_real_registry_is_consistent(self):
        errors = reg.check_registry()
        self.assertEqual(errors, [])

    def test_duplicate_entries_detected(self):
        original = reg.REGISTRY
        try:
            reg.REGISTRY = original + (original[0],)
            errors = reg.check_registry()
            self.assertTrue(any("duplicate" in error for error in errors))
        finally:
            reg.REGISTRY = original

    @staticmethod
    def _construct_bypassing_post_init(**fields):
        """Builds a MigrationStep instance while bypassing its own
        __post_init__ validation entirely (frozen dataclasses still allow
        object.__new__ + object.__setattr__) -- used only to prove
        check_registry()'s own independent re-audit still catches a
        malformed entry that somehow ended up in REGISTRY without ever
        going through the normal, validating constructor (defense in
        depth: check_registry() must not simply assume every entry was
        necessarily built the normal way)."""
        defaults = dict(
            epoch_from=1, epoch_to=2, compat_epoch_from=1, compat_epoch_to=2,
            kind=reg.MECHANICAL, description="bad", manual_steps=(),
        )
        defaults.update(fields)
        step = object.__new__(reg.MigrationStep)
        for name, value in defaults.items():
            object.__setattr__(step, name, value)
        return step

    def test_bad_epoch_ordering_detected(self):
        # Note: unlike compat_epoch_to/compat_epoch_from (enforced at
        # construction time, see test_compat_epoch_ordering_rejected_at_
        # construction below), format-version epoch_to/epoch_from
        # ordering has only ever been a check_registry()-time concern
        # (matching this module's pre-existing, unchanged design) -- a
        # MigrationStep with a bad *format* ordering constructs without
        # raising; check_registry() is what must catch it.
        original = reg.REGISTRY
        try:
            bad_step = self._construct_bypassing_post_init(epoch_from=2, epoch_to=1)
            reg.REGISTRY = (bad_step,)
            errors = reg.check_registry()
            self.assertTrue(any("epoch_to must be greater" in error for error in errors))
        finally:
            reg.REGISTRY = original

    def test_bad_compat_epoch_ordering_detected(self):
        """Symmetric to test_bad_epoch_ordering_detected, for the new
        compat_epoch pair: check_registry() must independently re-audit
        compat_epoch_to > compat_epoch_from too, not merely format
        version ordering."""
        with self.assertRaises(ValueError):
            make_step(compat_epoch_from=2, compat_epoch_to=1, description="bad")
        original = reg.REGISTRY
        try:
            bad_step = self._construct_bypassing_post_init(compat_epoch_from=2, compat_epoch_to=1)
            reg.REGISTRY = (bad_step,)
            errors = reg.check_registry()
            self.assertTrue(any("compat_epoch_to must be greater" in error for error in errors))
        finally:
            reg.REGISTRY = original

    def test_mismatched_legacy_sentinel_detected(self):
        """check_registry() must independently re-audit the legacy/absent
        sentinel invariant too: epoch_from/compat_epoch_from must both be
        None together, never one None and the other a real number, even
        for an entry that bypassed the normal constructor."""
        original = reg.REGISTRY
        try:
            bad_step = self._construct_bypassing_post_init(epoch_from=None, compat_epoch_from=1, epoch_to=1)
            reg.REGISTRY = (bad_step,)
            errors = reg.check_registry()
            self.assertTrue(any("legacy/absent sentinel" in error for error in errors))
        finally:
            reg.REGISTRY = original


class DryRunTests(unittest.TestCase):
    def test_dry_run_eligible_legacy_source(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            code, message = reg.dry_run(step, source)
            self.assertEqual(code, 0, message)
            self.assertIn("eligible", message)

    def test_dry_run_not_eligible_for_garbage_source(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "garbage.sav"
            source.write_bytes(b"\x00" * sft.SRAM_SIZE)
            code, message = reg.dry_run(step, source)
            self.assertNotEqual(code, 0)
            self.assertIn("NOT eligible", message)

    def test_dry_run_eligible_older_format_version_source(self):
        """The 1 -> 2 entry's dry-run must accept a real
        SAVE_COMPAT_MIGRATABLE_OLDER source -- *not* 'SAVE_COMPAT_CURRENT'
        (a bare `is None` ternary would wrongly demand that; fixed
        alongside this registry's first real numbered-epoch_from entry)."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "older.sav"
            source.write_bytes(older_migratable_image())
            code, message = reg.dry_run(step, source)
            self.assertEqual(code, 0, message)
            self.assertIn("eligible", message)

    def test_dry_run_not_eligible_for_already_current_source_at_1_to_2(self):
        """A source already at the live current epoch is NOT what the
        1 -> 2 step's dry-run should call eligible (it is not a
        SAVE_COMPAT_MIGRATABLE_OLDER source) -- this is the exact case
        the previous hardcoded 'SAVE_COMPAT_CURRENT' expectation got
        backwards for a numbered epoch_from."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "current.sav"
            source.write_bytes(current_image())
            code, message = reg.dry_run(step, source)
            self.assertNotEqual(code, 0)
            self.assertIn("NOT eligible", message)

    def test_dry_run_manual_step_refuses_without_reading_source(self):
        manual_step = make_step(
            kind=reg.MANUAL, description="future epoch bump",
            manual_steps=("do the thing by hand",),
        )
        code, message = reg.dry_run(manual_step, Path("/nonexistent/does/not/matter"))
        self.assertEqual(code, 4)
        self.assertIn("manual migration required", message)


class RunTests(unittest.TestCase):
    def test_run_out_of_place_success(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertEqual(code, 0, message)
            self.assertTrue(dest.is_file())
            # Source must be untouched (out-of-place only).
            self.assertEqual(source.read_bytes(), legacy_image())

    def test_run_none_to_1_produces_exact_epoch_1_not_live_epoch(self):
        """Issue #9 residual-hardening reproducer: a fresh, independent
        verifier reproduced this registry's declared `None -> 1` entry
        actually invoking save_format_tool.py's migrate with no way to
        tell it which epoch was being asked for -- it always stamped
        whatever config.mk's live epoch happens to be (today, epoch 2),
        so `epoch_to=1` was never actually reachable/verifiable as its
        own declared transition. This must now produce a genuine
        formatVersion 1 image (classifying SAVE_COMPAT_MIGRATABLE_OLDER
        against today's live epoch 2 config -- never SAVE_COMPAT_CURRENT,
        which would misrepresent it as the live epoch)."""
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertEqual(code, 0, message)
            produced = dest.read_bytes()
            meta = sft.ExpansionSaveMeta.unpack(
                produced[sft.META_OFFSET:sft.META_OFFSET + sft.META_SIZE]
            )
            self.assertEqual(meta.format_version, 1)
            live_epoch = sft.resolve_save_compat_epoch(ROOT)
            self.assertEqual(sft.classify_image(produced, live_epoch), sft.SAVE_COMPAT_MIGRATABLE_OLDER)

    def test_run_rejects_wrong_source_for_none_to_1_step(self):
        """A source that is already at formatVersion 1 (i.e. exactly the
        1 -> 2 step's own epoch_from, not this step's declared `None`
        epoch_from) must be rejected by the `None -> 1` step before any
        mutation -- guessing/accepting any broadly-migratable source
        regardless of which specific transition was requested is exactly
        the "no source-state guessing" gap this closes."""
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "already-epoch-1.sav"
            source.write_bytes(older_migratable_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertNotEqual(code, 0)
            self.assertFalse(dest.exists())
            # No partial mutation: source itself is also untouched.
            self.assertEqual(source.read_bytes(), older_migratable_image())

    def test_run_rejects_wrong_source_for_1_to_2_step(self):
        """Symmetric reproducer: a legacy/v0 source (this registry's
        `None -> 1` step's own epoch_from) must be rejected by the
        `1 -> 2` step, which declares a different, numbered epoch_from."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertNotEqual(code, 0)
            self.assertFalse(dest.exists())
            self.assertEqual(source.read_bytes(), legacy_image())

    def test_run_rejects_already_current_source_for_1_to_2_step(self):
        """A source already at the live current epoch is not this step's
        declared epoch_from=1 (SAVE_COMPAT_MIGRATABLE_OLDER) either."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "current.sav"
            source.write_bytes(current_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertNotEqual(code, 0)
            self.assertFalse(dest.exists())

    def test_run_detects_forged_success_with_wrong_epoch(self):
        """Adversarial: even if the underlying subprocess claims success
        (exit 0) while the destination it actually wrote does not match
        the declared step.epoch_to (e.g. a future save_format_tool.py
        regression reintroducing the live-epoch-collapse bug), run()'s
        own independent re-read/re-verify of the *published* destination
        must still catch the mismatch and fail -- never trusting the
        subprocess's self-reported exit code alone."""
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            dest = Path(tmp) / "migrated.sav"
            # Forge a "successful" migration that actually wrote a live
            # epoch-2 (current) image to dest, simulating exactly the
            # original bug this issue closes.
            dest.write_bytes(current_image())

            fake_result = mock.Mock(returncode=0, stdout="migrated (forged)\n", stderr="")
            with mock.patch.object(reg.subprocess, "run", return_value=fake_result) as run_mock:
                code, message = reg.run(step, source, dest)
            run_mock.assert_called_once()
            self.assertNotEqual(code, 0, message)
            self.assertIn("formatVersion", message)
            self.assertIn("2", message)

    def test_run_passes_declared_target_pair_and_expect_to_the_tool(self):
        """run()'s subprocess invocation must always carry an explicit
        --to-format-version, --to-compat-epoch, and --expect for the step
        being executed -- this is the actual mechanism that makes the
        declared transition an executable contract rather than an
        implicit, guessed one. The conflating --to-epoch shorthand must
        never be used here: formatVersion and compatEpoch targets are
        always passed independently."""
        step = reg.find_step(1, 2)
        # Precompute the forged "current" destination bytes *before*
        # patching subprocess.run: current_image() itself shells out to a
        # real subprocess (via build_current_expansion_save_meta()'s
        # build-commit resolution), and patching the global subprocess
        # module's run() would otherwise also intercept that unrelated
        # call -- this keeps the mock scoped to exactly the one call
        # under test.
        forged_current_bytes = current_image()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "older.sav"
            source.write_bytes(older_migratable_image())
            dest = Path(tmp) / "migrated.sav"

            def _capture(args, **kwargs):
                dest.write_bytes(forged_current_bytes)
                return mock.Mock(returncode=0, stdout="migrated (forged)\n", stderr="")

            with mock.patch.object(reg.subprocess, "run", side_effect=_capture) as run_mock:
                reg.run(step, source, dest, force=True)
            called_args = run_mock.call_args[0][0]
            self.assertNotIn("--to-epoch", called_args)
            self.assertIn("--to-format-version", called_args)
            self.assertEqual(called_args[called_args.index("--to-format-version") + 1], "2")
            self.assertIn("--to-compat-epoch", called_args)
            self.assertEqual(called_args[called_args.index("--to-compat-epoch") + 1], "2")
            self.assertIn("--expect", called_args)
            self.assertEqual(
                called_args[called_args.index("--expect") + 1], sft.SAVE_COMPAT_MIGRATABLE_OLDER
            )

    def test_run_refuses_same_source_and_destination(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            code, message = reg.run(step, source, source)
            self.assertEqual(code, 6)
            self.assertIn("out-of-place", message)

    def test_run_migrates_older_format_version_source_to_current(self):
        """The real 1 -> 2 registry entry, end to end: a genuine
        SAVE_COMPAT_MIGRATABLE_OLDER source (formatVersion one behind
        current) migrates out-of-place to a destination that re-classifies
        SAVE_COMPAT_CURRENT -- proving this registry's wiring (not just
        save_format_tool.py's own, separately-tested migrate command)
        actually reaches the real tool for a numbered epoch_from."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "older.sav"
            source.write_bytes(older_migratable_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertEqual(code, 0, message)
            self.assertTrue(dest.is_file())
            # Source must be untouched (out-of-place only).
            self.assertEqual(source.read_bytes(), older_migratable_image())
            save_compat_epoch = sft.resolve_save_compat_epoch(ROOT)
            dest_state = sft.classify_image(dest.read_bytes(), save_compat_epoch)
            self.assertEqual(dest_state, sft.SAVE_COMPAT_CURRENT)

    def test_run_manual_step_refuses(self):
        manual_step = make_step(
            kind=reg.MANUAL, description="future epoch bump",
            manual_steps=("step one", "step two"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.sav"
            source.write_bytes(current_image())
            dest = Path(tmp) / "b.sav"
            code, message = reg.run(manual_step, source, dest)
            self.assertEqual(code, 4)
            self.assertIn("step one", message)
            self.assertFalse(dest.exists())

    def test_run_never_touches_real_user_save_fixtures_directory(self):
        # This test asserts the *contract*, not a real save: every fixture
        # in this module is built in memory (legacy_image()/current_image()),
        # never read from a committed binary blob.
        self.assertIsInstance(legacy_image(), bytes)
        self.assertIsInstance(current_image(), bytes)


class ExactSourceEpochEnforcementTests(unittest.TestCase):
    """Issue #9 residual-hardening reproducer (finding C): a fresh audit
    found that `--expect SAVE_COMPAT_MIGRATABLE_OLDER` alone -- the
    `1 -> 2` step's own declared precondition -- is a *broad*
    classification bucket ('raw formatVersion below today's live
    SAVE_FORMAT_VERSION_CURRENT'), not an exact-epoch check: a forged or
    corrupt source whose real, checksum-valid on-media formatVersion is
    0 (not 1) used to be silently accepted and migrated forward by the
    declared `epoch_from=1` step, exactly as if it had genuinely been a
    real epoch-1 save. These reproduce the pre-fix bypass shape directly
    (`dry_run`/`run` must both reject it, before any mutation) and prove
    the real epoch-1 case still passes unaffected."""

    def test_dry_run_rejects_wrong_numbered_epoch_within_the_same_broad_bucket(self):
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "forged-epoch0.sav"
            source.write_bytes(forged_exact_epoch_image(0))
            code, message = reg.dry_run(step, source)
            self.assertNotEqual(code, 0)
            self.assertIn("NOT eligible", message)
            self.assertIn("formatVersion is exactly 0", message)
            self.assertIn("epoch_from 1", message)

    def test_run_rejects_wrong_numbered_epoch_within_the_same_broad_bucket(self):
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "forged-epoch0.sav"
            forged = forged_exact_epoch_image(0)
            source.write_bytes(forged)
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertNotEqual(code, 0)
            self.assertIn("formatVersion is exactly 0", message)
            # No partial mutation whatsoever: no destination, source untouched.
            self.assertFalse(dest.exists())
            self.assertEqual(source.read_bytes(), forged)

    def test_run_still_accepts_the_genuine_exact_epoch_1_source(self):
        """Symmetric control: this hardening must never reject the real,
        declared epoch_from=1 source it is supposed to accept -- only the
        wrong-numbered-epoch-in-the-same-bucket forgery above."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "genuine-epoch1.sav"
            source.write_bytes(forged_exact_epoch_image(1))
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertEqual(code, 0, message)
            self.assertTrue(dest.is_file())
            produced_meta = sft.ExpansionSaveMeta.unpack(
                dest.read_bytes()[sft.META_OFFSET:sft.META_OFFSET + sft.META_SIZE]
            )
            self.assertEqual(produced_meta.format_version, 2)

    def test_exact_epoch_check_never_applies_to_the_none_epoch_from_step(self):
        """The `None -> 1` step's own `SAVE_COMPAT_VALID_LEGACY_OR_
        VANILLA` precondition is already exact/unambiguous (no numbered
        epoch to further narrow) -- `_exact_source_state_mismatch` must
        always defer to it rather than inventing a spurious numbered
        check for a `None` epoch_from."""
        step = reg.find_step(None, 1)
        self.assertIsNone(reg._exact_source_state_mismatch(step, Path("/nonexistent")))

    def test_dry_run_still_accepts_a_garbage_source_via_the_ordinary_path(self):
        """A source with no trustworthy on-media record at all (blank/
        EMPTY) has nothing for the new exact-epoch check to independently
        confirm -- it must fall through to the ordinary `--expect`
        classification check unchanged, still failing closed exactly as
        before this hardening."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "garbage.sav"
            source.write_bytes(b"\x00" * sft.SRAM_SIZE)
            code, message = reg.dry_run(step, source)
            self.assertNotEqual(code, 0)
            self.assertIn("NOT eligible", message)


class ExactSourceCompatEpochEnforcementTests(unittest.TestCase):
    """Issue #9 residual-hardening reproducer (finding D, the actual
    exploit shape this task description names): a checksum-valid source
    whose raw formatVersion genuinely matches a declared step's
    epoch_from is NOT sufficient proof on its own -- its raw compatEpoch
    must independently match too. `classify_save_compat_raw()` never even
    inspects compatEpoch once formatVersion has already resolved the
    state to SAVE_COMPAT_MIGRATABLE_OLDER, so a forged source with
    formatVersion=1 (this registry's real, declared epoch_from for its
    1 -> 2 entry) but compatEpoch=999 (nowhere close to the declared
    compat_epoch_from=1) used to be silently accepted end to end -- both
    the broad --expect bucket *and* the pre-hardening exact-epoch check
    (formatVersion only) approved it."""

    def test_dry_run_rejects_correct_format_wrong_compat_epoch(self):
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "format1-epoch999.sav"
            source.write_bytes(forged_exact_pair_image(format_version=1, compat_epoch=999))
            code, message = reg.dry_run(step, source)
            self.assertNotEqual(code, 0)
            self.assertIn("NOT eligible", message)
            self.assertIn("compatEpoch is exactly 999", message)
            self.assertIn("compat_epoch_from 1", message)

    def test_run_rejects_correct_format_wrong_compat_epoch_before_any_mutation(self):
        """The exact reproducer named by this hardening's own task
        description: formatVersion=1 (genuinely matching epoch_from=1),
        compatEpoch=999 (nowhere near compat_epoch_from=1). Must be
        rejected by run() before any subprocess is invoked at all, with
        no destination created and the source left byte-for-byte
        untouched."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "format1-epoch999.sav"
            forged = forged_exact_pair_image(format_version=1, compat_epoch=999)
            source.write_bytes(forged)
            dest = Path(tmp) / "migrated.sav"
            with mock.patch.object(reg.subprocess, "run") as run_mock:
                code, message = reg.run(step, source, dest)
            run_mock.assert_not_called()
            self.assertNotEqual(code, 0)
            self.assertIn("compatEpoch is exactly 999", message)
            self.assertIn("compat_epoch_from 1", message)
            self.assertFalse(dest.exists())
            self.assertEqual(source.read_bytes(), forged)

    def test_dry_run_rejects_wrong_format_correct_compat_epoch(self):
        """Symmetric reproducer: formatVersion=0 (wrong -- this step
        declares epoch_from=1), compatEpoch=1 (correct, matches
        compat_epoch_from=1) -- the formatVersion mismatch alone must
        still be caught (checked first), proving neither field alone is
        trusted over the other."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "format0-epoch1.sav"
            source.write_bytes(forged_exact_pair_image(format_version=0, compat_epoch=1))
            code, message = reg.dry_run(step, source)
            self.assertNotEqual(code, 0)
            self.assertIn("NOT eligible", message)
            self.assertIn("formatVersion is exactly 0", message)
            self.assertIn("epoch_from 1", message)

    def test_run_rejects_wrong_format_correct_compat_epoch_before_any_mutation(self):
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "format0-epoch1.sav"
            forged = forged_exact_pair_image(format_version=0, compat_epoch=1)
            source.write_bytes(forged)
            dest = Path(tmp) / "migrated.sav"
            with mock.patch.object(reg.subprocess, "run") as run_mock:
                code, message = reg.run(step, source, dest)
            run_mock.assert_not_called()
            self.assertNotEqual(code, 0)
            self.assertIn("formatVersion is exactly 0", message)
            self.assertFalse(dest.exists())
            self.assertEqual(source.read_bytes(), forged)

    def test_run_still_accepts_the_genuine_exact_pair_source(self):
        """Symmetric control: this hardening must never reject the real,
        declared (epoch_from=1, compat_epoch_from=1) source it is
        supposed to accept -- only a wrong-numbered-field forgery."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "genuine-1-1.sav"
            source.write_bytes(forged_exact_pair_image(format_version=1, compat_epoch=1))
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertEqual(code, 0, message)
            produced_meta = sft.ExpansionSaveMeta.unpack(
                dest.read_bytes()[sft.META_OFFSET:sft.META_OFFSET + sft.META_SIZE]
            )
            self.assertEqual(produced_meta.format_version, 2)
            self.assertEqual(produced_meta.compat_epoch, 2)


class EndToEndExactPairSuccessTests(unittest.TestCase):
    """Adversarial-suite requirement: both real registered transitions,
    end to end, verified on *both* fields (not just formatVersion) --
    "exact legacy -> format1/epoch1 success" and "format1/epoch1 ->
    format2/epoch2 success"."""

    def test_legacy_to_format1_epoch1_success(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertEqual(code, 0, message)
            meta = sft.ExpansionSaveMeta.unpack(
                dest.read_bytes()[sft.META_OFFSET:sft.META_OFFSET + sft.META_SIZE]
            )
            self.assertEqual(meta.format_version, 1)
            self.assertEqual(meta.compat_epoch, 1)

    def test_format1_epoch1_to_format2_epoch2_success(self):
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "older.sav"
            source.write_bytes(older_migratable_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertEqual(code, 0, message)
            meta = sft.ExpansionSaveMeta.unpack(
                dest.read_bytes()[sft.META_OFFSET:sft.META_OFFSET + sft.META_SIZE]
            )
            self.assertEqual(meta.format_version, 2)
            self.assertEqual(meta.compat_epoch, 2)


class ForgedTargetOutputTests(unittest.TestCase):
    """Adversarial-suite requirement: 'forged output target format2/
    epoch999 and format999/epoch2 rejected' -- even when the underlying
    subprocess reports success (exit 0) and one of the two target fields
    is correct, run()'s own independent re-read/re-verify of the
    *published* destination must catch a mismatch on either field alone
    and fail, never trusting the subprocess's self-reported exit code or
    just one of the two raw fields."""

    def _forge_dest(self, dest: Path, format_version: int, compat_epoch: int) -> bytes:
        meta = sft.ExpansionSaveMeta(
            magic=sft.META_MAGIC,
            format_version=format_version,
            compat_epoch=compat_epoch,
            abi_id=sft.SAVE_ABI_ID_AAPCS,
            framework_version_packed=0x000100,
            config_fingerprint=b"deadbeefcafebabe\x00",
            build_commit_short=b"cafef00d\x00",
            checksum=0,
            reserved=b"\x00" * (sft.META_SIZE - sft.META_CHECKSUM_DOMAIN - 2),
        )
        meta.checksum = meta.computed_checksum()
        forged_bytes = bytes(make_image(make_header(valid=True), meta.pack()))
        dest.write_bytes(forged_bytes)
        return forged_bytes

    def test_forged_output_correct_format_wrong_compat_epoch_rejected(self):
        """Declared target is (formatVersion=2, compatEpoch=2); the
        forged output has the correct formatVersion (2) but a bogus
        compatEpoch (999) -- must still be rejected."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "older.sav"
            source.write_bytes(older_migratable_image())
            dest = Path(tmp) / "migrated.sav"

            def _capture(args, **kwargs):
                self._forge_dest(dest, format_version=2, compat_epoch=999)
                return mock.Mock(returncode=0, stdout="migrated (forged)\n", stderr="")

            with mock.patch.object(reg.subprocess, "run", side_effect=_capture):
                code, message = reg.run(step, source, dest, force=True)
            self.assertNotEqual(code, 0, message)
            self.assertIn("compatEpoch", message)
            self.assertIn("999", message)
            self.assertIn("compat_epoch_to", message)

    def test_forged_output_wrong_format_correct_compat_epoch_rejected(self):
        """Declared target is (formatVersion=2, compatEpoch=2); the
        forged output has a bogus formatVersion (200 -- struct
        ExpansionSaveMeta's on-media formatVersion is a single byte, so
        the largest distinguishable-from-2 value is used here rather than
        an out-of-byte-range 999) but the correct compatEpoch (2) -- must
        still be rejected (formatVersion is checked first, so this is
        caught by that check)."""
        step = reg.find_step(1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "older.sav"
            source.write_bytes(older_migratable_image())
            dest = Path(tmp) / "migrated.sav"

            def _capture(args, **kwargs):
                self._forge_dest(dest, format_version=200, compat_epoch=2)
                return mock.Mock(returncode=0, stdout="migrated (forged)\n", stderr="")

            with mock.patch.object(reg.subprocess, "run", side_effect=_capture):
                code, message = reg.run(step, source, dest, force=True)
            self.assertNotEqual(code, 0, message)
            self.assertIn("formatVersion", message)
            self.assertIn("200", message)
            self.assertIn("epoch_to", message)


class CliTests(unittest.TestCase):
    def test_check_cli_ok(self):
        self.assertEqual(reg.main(["check"]), 0)

    def test_list_cli_ok(self):
        self.assertEqual(reg.main(["list"]), 0)


if __name__ == "__main__":
    unittest.main()
