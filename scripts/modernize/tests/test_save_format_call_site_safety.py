"""Regression coverage for issue #2 slice 1's review-fix #2: the shared
`EnsureGlobalSaveInfoLoaded()` safe-init helper (src/bmsave-lib.c) and its
two gameplay call sites (src/classchg-sel.c's `Check3rdTraineeEnabled` and
src/bmsave-bwl.c's `SavePlayThroughData`).

Both call sites used to do:

    if (!ReadGlobalSaveInfo(&info)) {
        InitGlobalSaveInfodata();
        ReadGlobalSaveInfo(&info);
    }

which silently treated "the header struct failed to read" as "SRAM is
genuinely blank" -- the same class of bug `EraseSramDataIfInvalid()` had
at boot, just reachable later from class-change/chapter-completion. They
now both go through `EnsureGlobalSaveInfoLoaded()`, which only
initializes on `SAVE_COMPAT_EMPTY` and otherwise refuses (returns false)
without touching or reinterpreting SRAM.

This module has two layers of proof, since no ARM/GBA execution
environment is available in this sandbox (see docs/save_format.md's
"Known infrastructure gaps"):

1. Static source-scan tests (regex over the real, shipped .c files) that
   fail immediately if the unsafe pattern is reintroduced, or if either
   call site stops routing through the shared helper, or if the helper's
   own guard stops being `SAVE_COMPAT_EMPTY`-only.
2. A byte-exact behavioral mirror of `EnsureGlobalSaveInfoLoaded()`'s
   control flow (reusing `save_format_tool`'s already byte-exact
   `classify_save_compat_raw()` mirror of the real C classifier), proving
   for all 8 classifier states that initialization only ever happens for
   `SAVE_COMPAT_EMPTY` -- i.e. that nonblank invalid SRAM can never be
   wiped by this helper, no matter which non-empty state it's in.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import save_format_tool as sft  # noqa: E402

from test_save_format_tool import make_header, make_meta  # noqa: E402


BMSAVE_LIB_C = ROOT / "src" / "bmsave-lib.c"
CLASSCHG_SEL_C = ROOT / "src" / "classchg-sel.c"
BMSAVE_BWL_C = ROOT / "src" / "bmsave-bwl.c"
BMSAVE_H = ROOT / "include" / "bmsave.h"

# The exact unsafe pattern that used to exist at both call sites: a
# failed ReadGlobalSaveInfo() unconditionally followed by
# InitGlobalSaveInfodata(). This must never reappear anywhere in the
# tree (grep the whole src/ directory, not just the two known files).
_UNSAFE_PATTERN = re.compile(
    r"if\s*\(\s*!\s*ReadGlobalSaveInfo\s*\([^)]*\)\s*\)\s*\{\s*"
    r"InitGlobalSaveInfodata\s*\(\s*\)\s*;",
    re.MULTILINE,
)


class SourceScanTests(unittest.TestCase):
    """Static proof (no compilation/execution needed) that the unsafe
    pattern is gone and both call sites route through the shared,
    classifier-gated helper."""

    def test_unsafe_pattern_absent_from_whole_src_tree(self):
        src_dir = ROOT / "src"
        offenders = []
        for c_file in sorted(src_dir.glob("*.c")):
            text = c_file.read_text(encoding="utf-8", errors="replace")
            if _UNSAFE_PATTERN.search(text):
                offenders.append(c_file.name)
        self.assertEqual(
            offenders, [],
            f"unsafe 'failed read == blank SRAM' pattern reintroduced in: {offenders}",
        )

    def test_check_3rd_trainee_enabled_uses_shared_helper(self):
        text = CLASSCHG_SEL_C.read_text(encoding="utf-8")
        match = re.search(
            r"bool Check3rdTraineeEnabled\(void\)\s*\{(.*?)\n\}",
            text, re.DOTALL,
        )
        self.assertIsNotNone(match, "Check3rdTraineeEnabled() not found")
        body = match.group(1)
        self.assertIn("EnsureGlobalSaveInfoLoaded", body)
        self.assertNotIn("InitGlobalSaveInfodata", body)

    def test_save_play_through_data_uses_shared_helper(self):
        text = BMSAVE_BWL_C.read_text(encoding="utf-8")
        match = re.search(
            r"void SavePlayThroughData\(void\)\s*\{(.*?)\n\}",
            text, re.DOTALL,
        )
        self.assertIsNotNone(match, "SavePlayThroughData() not found")
        body = match.group(1)
        self.assertIn("EnsureGlobalSaveInfoLoaded", body)
        self.assertNotIn("InitGlobalSaveInfodata", body)

    def test_ensure_global_save_info_loaded_is_declared(self):
        text = BMSAVE_H.read_text(encoding="utf-8")
        self.assertIn("bool EnsureGlobalSaveInfoLoaded(struct GlobalSaveInfo *buf);", text)

    def test_ensure_global_save_info_loaded_guard_is_empty_only(self):
        """The shared helper's own re-init guard must still be exactly
        `SAVE_COMPAT_EMPTY == ClassifySramSaveCompat()` (or the
        equivalent left-hand form) -- if a future edit widens this to
        also trigger on e.g. HEADER_CORRUPT, this test must fail."""
        text = BMSAVE_LIB_C.read_text(encoding="utf-8")
        match = re.search(
            r"bool EnsureGlobalSaveInfoLoaded\(struct GlobalSaveInfo \*buf\)\s*\{(.*?)\n\}",
            text, re.DOTALL,
        )
        self.assertIsNotNone(match, "EnsureGlobalSaveInfoLoaded() not found in bmsave-lib.c")
        body = match.group(1)

        guard = re.search(
            r"if\s*\(\s*(SAVE_COMPAT_EMPTY\s*!=\s*ClassifySramSaveCompat\s*\(\s*\)"
            r"|ClassifySramSaveCompat\s*\(\s*\)\s*!=\s*SAVE_COMPAT_EMPTY)\s*\)",
            body,
        )
        self.assertIsNotNone(
            guard,
            "EnsureGlobalSaveInfoLoaded() must gate re-init strictly on "
            "SAVE_COMPAT_EMPTY (found body: %r)" % body,
        )
        # Exactly one call to InitGlobalSaveInfodata() inside the helper
        # (ignoring /* ... */ comments, which may reference it in prose),
        # and it must be the only place in this function that can mutate
        # SRAM.
        body_no_comments = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        self.assertEqual(body_no_comments.count("InitGlobalSaveInfodata()"), 1)


def _read_global_save_info_would_succeed(header_bytes):
    """Host-side mirror of ReadGlobalSaveInfo()'s success condition: it
    only depends on the struct GlobalSaveInfo header region (name marker
    / magic32 / magic16 / checksum) -- never on the expansion metadata
    pad, since that struct predates issue #2 entirely."""
    if len(header_bytes) < sft.HEADER_CHECKSUM_DOMAIN:
        return False
    if header_bytes[0:8] != sft.HEADER_NAME_MARKER:
        return False
    magic32 = int.from_bytes(header_bytes[8:12], "little")
    magic16 = int.from_bytes(header_bytes[12:14], "little")
    if magic32 != sft.SAVEMAGIC32 or magic16 != sft.SAVEMAGIC16:
        return False
    checksum = int.from_bytes(header_bytes[0x60:0x62], "little")
    return checksum == sft.checksum16(bytes(header_bytes[: sft.HEADER_CHECKSUM_DOMAIN]))


def _ensure_global_save_info_loaded_would_init(header_bytes, meta_bytes, save_compat_epoch):
    """Host-side behavioral mirror of EnsureGlobalSaveInfoLoaded()'s
    control flow. Returns (would_succeed_without_init, would_call_init).

    This exists purely to prove the *decision* the real C helper makes
    (init vs. refuse vs. succeed-as-is) for every classifier state,
    reusing the already byte-exact classify_save_compat_raw() mirror as
    the source of truth for the classification itself.
    """
    if _read_global_save_info_would_succeed(header_bytes):
        return True, False

    state = sft.classify_save_compat_raw(header_bytes, meta_bytes, save_compat_epoch)
    would_init = state == sft.SAVE_COMPAT_EMPTY
    return would_init, would_init


class EnsureGlobalSaveInfoLoadedBehaviorTests(unittest.TestCase):
    """Proves, for every one of the 8 raw classifier states, that the
    shared safe-init helper never initializes/wipes except when the
    state is genuinely SAVE_COMPAT_EMPTY."""

    def setUp(self):
        self.epoch = sft.resolve_save_compat_epoch(ROOT)

    def _assert_never_inits_on_nonblank(self, header, meta, expected_state):
        state = sft.classify_save_compat_raw(bytes(header), bytes(meta), self.epoch)
        self.assertEqual(state, expected_state)
        succeeds, would_init = _ensure_global_save_info_loaded_would_init(
            bytes(header), bytes(meta), self.epoch
        )
        self.assertFalse(
            would_init,
            f"EnsureGlobalSaveInfoLoaded() must never wipe/init on {expected_state}",
        )

    def test_empty_sram_is_the_only_state_that_inits(self):
        header = make_header(valid=False)
        for i in range(len(header)):
            header[i] = 0xFF
        meta = make_meta(present=False)  # all 0xFF -- genuinely blank
        state = sft.classify_save_compat_raw(bytes(header), bytes(meta), self.epoch)
        self.assertEqual(state, sft.SAVE_COMPAT_EMPTY)
        succeeds, would_init = _ensure_global_save_info_loaded_would_init(
            bytes(header), bytes(meta), self.epoch
        )
        self.assertTrue(would_init, "genuinely blank SRAM must still be initializable")

    def test_header_corrupt_never_inits(self):
        header = make_header(valid=False)
        meta = make_meta(present=False)
        self._assert_never_inits_on_nonblank(header, meta, sft.SAVE_COMPAT_HEADER_CORRUPT)

    def test_valid_legacy_or_vanilla_reads_successfully_without_init(self):
        header = make_header(valid=True)
        meta = make_meta(present=False)
        state = sft.classify_save_compat_raw(bytes(header), bytes(meta), self.epoch)
        self.assertEqual(state, sft.SAVE_COMPAT_VALID_LEGACY_OR_VANILLA)
        succeeds, would_init = _ensure_global_save_info_loaded_would_init(
            bytes(header), bytes(meta), self.epoch
        )
        self.assertTrue(succeeds)
        self.assertFalse(would_init)

    def test_metadata_corrupt_never_inits(self):
        header = make_header(valid=True)
        meta = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT, compat_epoch=self.epoch, corrupt_checksum=True
        )
        self._assert_never_inits_on_nonblank(header, meta, sft.SAVE_COMPAT_METADATA_CORRUPT)

    def test_current_never_inits(self):
        header = make_header(valid=True)
        meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT, compat_epoch=self.epoch)
        self._assert_never_inits_on_nonblank(header, meta, sft.SAVE_COMPAT_CURRENT)

    def test_migratable_older_never_inits(self):
        header = make_header(valid=True)
        meta = make_meta(format_version=0, compat_epoch=self.epoch)
        self._assert_never_inits_on_nonblank(header, meta, sft.SAVE_COMPAT_MIGRATABLE_OLDER)

    def test_newer_unsupported_never_inits(self):
        header = make_header(valid=True)
        meta = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT + 1, compat_epoch=self.epoch
        )
        self._assert_never_inits_on_nonblank(header, meta, sft.SAVE_COMPAT_NEWER_UNSUPPORTED)

    def test_save_config_incompatible_never_inits(self):
        header = make_header(valid=True)
        meta = make_meta(format_version=sft.SAVE_FORMAT_VERSION_CURRENT, compat_epoch=self.epoch + 1)
        self._assert_never_inits_on_nonblank(
            header, meta, sft.SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE
        )


if __name__ == "__main__":
    unittest.main()
