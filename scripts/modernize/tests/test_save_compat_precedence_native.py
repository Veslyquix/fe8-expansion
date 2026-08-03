"""Regression lock for `ClassifySaveCompatRaw()`'s classification
precedence order (issue #18 sprint 2 Sprint-2-review fix).

The bug this guards against: a save whose `formatVersion` is older than
current *and* whose `compatEpoch` also happens to be stale at the same
time -- exactly a genuine pre-sprint-2 save (`formatVersion` 1,
`compatEpoch` 1) read by a build now at `SAVE_FORMAT_VERSION_CURRENT` 2 /
`FE8_EXPANSION_SAVE_COMPAT_EPOCH` 2 -- must classify
`SAVE_COMPAT_MIGRATABLE_OLDER`, never `SAVE_COMPAT_SAVE_CONFIG_
INCOMPATIBLE`. `ClassifySaveCompatRaw()` (src/bmsave-lib.c) checks
`formatVersion` strictly *before* `compatEpoch`, so an older `formatVersion`
alone always resolves the classification first; `compatEpoch` is never
even read in that case.

docs/save_format.md's "Format / compatibility bump table" previously (pre-
review-fix) misdescribed this exact scenario as classifying
`SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE`. This module locks the correct
behavior three independent ways so that regression can never silently
creep back in:

1. Extracts+compiles+runs the *real* `ClassifySaveCompatRaw()` verbatim
   from `src/bmsave-lib.c` (host-native `cc`, not agbcc/ARM -- the same
   pattern already established by `test_save_format_meta_bytes_native.py`
   / `test_expansion_user_prefs_native.py`) against a v1/epoch1 fixture,
   proving the real, shipped C function itself returns
   `SAVE_COMPAT_MIGRATABLE_OLDER` -- not merely a hand-maintained mirror.
2. Cross-checks `scripts/modernize/save_format_tool.py`'s own byte-exact
   Python mirror (`classify_save_compat_raw()`) for the identical inputs.
3. Greps `docs/save_format.md`'s corrected bump-table wording, so a future
   accidental revert of that doc fix fails this suite immediately rather
   than silently reintroducing the same factual error.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import save_format_tool as sft  # noqa: E402
import expansion_config as ec  # noqa: E402

from test_save_format_meta_bytes_native import (  # noqa: E402
    _extract_c_function,
    _extract_struct,
)
from test_save_format_tool import make_header, make_meta  # noqa: E402

DOCS_PATH = ROOT / "docs" / "save_format.md"


class ClassifySaveCompatRawPrecedenceNativeTests(unittest.TestCase):
    """Compiles+runs the real C `ClassifySaveCompatRaw()` natively (host
    `cc`, not agbcc/ARM) against controlled formatVersion/compatEpoch
    combinations and compares its classification to the Python mirror's
    output for the identical inputs."""

    @classmethod
    def setUpClass(cls):
        cc = "cc"
        try:
            subprocess.run([cc, "--version"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, check=True)
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest("no host 'cc' compiler available")
        cls.cc = cc

        cls.bmsave_h = (ROOT / "include" / "bmsave.h").read_text(encoding="utf-8")
        cls.save_format_h = (ROOT / "include" / "save_format.h").read_text(encoding="utf-8")
        cls.bmsave_lib_c = (ROOT / "src" / "bmsave-lib.c").read_text(encoding="utf-8")
        cls.bmlib_c = (ROOT / "src" / "bmlib.c").read_text(encoding="utf-8")

        # This build's real, configured epoch (config.mk), exactly as
        # save_format_tool.py itself resolves it -- never hardcoded, so
        # this test tracks the repo instead of a stale snapshot of it.
        cls.epoch = ec.validate_save_compat_epoch(
            ec.parse_config_mk(ROOT / "config.mk")["EXPANSION_SAVE_COMPAT_EPOCH"]
        )

    def _build_probe_binary(self, tmp_path: Path) -> Path:
        global_save_info_struct = _extract_struct(self.bmsave_h, "GlobalSaveInfo")
        expansion_save_meta_struct = _extract_struct(self.save_format_h, "ExpansionSaveMeta")

        string_compare_fn = _extract_c_function(self.bmlib_c, "StringCompare")
        checksum16_fn = _extract_c_function(self.bmsave_lib_c, "Checksum16")
        bytes_equal_fn = _extract_c_function(self.bmsave_lib_c, "BytesEqual")
        meta_checksum_fn = _extract_c_function(self.bmsave_lib_c, "ExpansionSaveMetaChecksum")
        classify_fn = _extract_c_function(self.bmsave_lib_c, "ClassifySaveCompatRaw")

        probe_source = f"""\
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int8_t s8;
typedef s8 bool;
typedef u8 bool8;
enum {{ false, true }};

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

#define STRUCT_PAD(from, to) unsigned char _pad_ ## from[(to) - (from)]
#define MAX_SAVED_GAME_CLEARS 12

{global_save_info_struct};

enum bmsave_magics_fe8 {{
    SAVEMAGIC16       = 0x200A,
    SAVEMAGIC32       = 0x40624
}};

#define GLOBALSIZEINFO_SIZE_FOR_CHECKSUM 0x50

#define EXPANSION_SAVE_META_MAGIC "FSAV"
#define EXPANSION_SAVE_META_MAGIC_SIZE 4
#define SAVE_FORMAT_VERSION_CURRENT {sft.SAVE_FORMAT_VERSION_CURRENT}
#define EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM 0x2E
#define FE8_EXPANSION_SAVE_COMPAT_EPOCH {self.epoch}

{expansion_save_meta_struct};

enum SaveCompatState {{
    SAVE_COMPAT_EMPTY,
    SAVE_COMPAT_VALID_LEGACY_OR_VANILLA,
    SAVE_COMPAT_HEADER_CORRUPT,
    SAVE_COMPAT_METADATA_CORRUPT,
    SAVE_COMPAT_CURRENT,
    SAVE_COMPAT_MIGRATABLE_OLDER,
    SAVE_COMPAT_NEWER_UNSUPPORTED,
    SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE
}};

static const char sSaveMarker[] = "AGB-FE9";

{string_compare_fn}

{checksum16_fn}

{bytes_equal_fn}

{meta_checksum_fn}

{classify_fn}

static const char *StateName(enum SaveCompatState state)
{{
    switch (state) {{
    case SAVE_COMPAT_EMPTY: return "SAVE_COMPAT_EMPTY";
    case SAVE_COMPAT_VALID_LEGACY_OR_VANILLA: return "SAVE_COMPAT_VALID_LEGACY_OR_VANILLA";
    case SAVE_COMPAT_HEADER_CORRUPT: return "SAVE_COMPAT_HEADER_CORRUPT";
    case SAVE_COMPAT_METADATA_CORRUPT: return "SAVE_COMPAT_METADATA_CORRUPT";
    case SAVE_COMPAT_CURRENT: return "SAVE_COMPAT_CURRENT";
    case SAVE_COMPAT_MIGRATABLE_OLDER: return "SAVE_COMPAT_MIGRATABLE_OLDER";
    case SAVE_COMPAT_NEWER_UNSUPPORTED: return "SAVE_COMPAT_NEWER_UNSUPPORTED";
    case SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE: return "SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE";
    }}
    return "?";
}}

int main(int argc, char **argv)
{{
    /* argv[1]=formatVersion argv[2]=compatEpoch -- both attacker/caller
     * supplied so one compiled probe binary covers every combination
     * this suite needs without recompiling per case. */
    struct GlobalSaveInfo header;
    struct ExpansionSaveMeta meta;
    enum SaveCompatState state;

    if (argc != 3)
        return 2;

    memset(&header, 0, sizeof(header));
    memset(&meta, 0, sizeof(meta));

    memcpy(header.name, sSaveMarker, sizeof(sSaveMarker));
    header.magic32 = SAVEMAGIC32;
    header.magic16 = SAVEMAGIC16;
    header.checksum = Checksum16(&header, GLOBALSIZEINFO_SIZE_FOR_CHECKSUM);

    memcpy(meta.magic, EXPANSION_SAVE_META_MAGIC, EXPANSION_SAVE_META_MAGIC_SIZE);
    meta.formatVersion = (u8)atoi(argv[1]);
    meta.compatEpoch = (u16)atoi(argv[2]);
    meta.checksum = ExpansionSaveMetaChecksum(&meta);

    state = ClassifySaveCompatRaw(&header, FALSE, &meta, FALSE);
    printf("%s\\n", StateName(state));
    return 0;
}}
"""

        source = tmp_path / "probe.c"
        binary = tmp_path / "probe"
        source.write_text(probe_source, encoding="utf-8")

        compile_cmd = [self.cc, "-std=c99", str(source), "-o", str(binary)]
        compile_result = subprocess.run(
            compile_cmd, cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        self.assertEqual(
            compile_result.returncode, 0,
            f"native ClassifySaveCompatRaw precedence probe failed to compile:\n"
            f"{compile_result.stdout}\n\n--- generated source ---\n{probe_source}",
        )
        return binary

    def _run_case(self, binary: Path, format_version: int, compat_epoch: int) -> str:
        result = subprocess.run(
            [str(binary), str(format_version), str(compat_epoch)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        self.assertEqual(result.returncode, 0, f"probe crashed: {result.stdout!r}")
        return result.stdout.decode("ascii").strip()

    def test_older_format_version_wins_over_stale_epoch_in_both_c_and_python(self):
        """The exact regression scenario: formatVersion older than current
        AND compatEpoch simultaneously stale -- a genuine pre-sprint-2
        (formatVersion 1, compatEpoch 1) save under this repo's real
        current formatVersion/epoch. Must be SAVE_COMPAT_MIGRATABLE_OLDER
        in both the real C function and the Python mirror, never
        SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE."""
        with tempfile.TemporaryDirectory() as tmp:
            binary = self._build_probe_binary(Path(tmp))

            older_format_version = sft.SAVE_FORMAT_VERSION_CURRENT - 1
            stale_epoch = self.epoch - 1 if self.epoch > 0 else self.epoch + 1
            self.assertNotEqual(stale_epoch, self.epoch)

            c_state = self._run_case(binary, older_format_version, stale_epoch)
            self.assertEqual(
                c_state, sft.SAVE_COMPAT_MIGRATABLE_OLDER,
                "real ClassifySaveCompatRaw() must resolve an older "
                "formatVersion before ever consulting compatEpoch",
            )
            self.assertNotEqual(
                c_state, sft.SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE,
                "a stale compatEpoch alongside an older formatVersion must "
                "never be reported as SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE",
            )

            header_bytes = bytes(make_header(valid=True))
            meta_bytes = bytes(make_meta(
                format_version=older_format_version, compat_epoch=stale_epoch,
            ))
            py_state = sft.classify_save_compat_raw(header_bytes, meta_bytes, self.epoch)

            self.assertEqual(py_state, sft.SAVE_COMPAT_MIGRATABLE_OLDER)
            self.assertEqual(c_state, py_state)

    def test_current_format_version_with_stale_epoch_is_still_config_incompatible(self):
        """Symmetric guard: SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE must still
        fire when formatVersion *is* current but compatEpoch alone is
        stale -- proving this fix only reorders precedence, never removes
        the config-incompatible state itself."""
        with tempfile.TemporaryDirectory() as tmp:
            binary = self._build_probe_binary(Path(tmp))
            stale_epoch = self.epoch - 1 if self.epoch > 0 else self.epoch + 1

            c_state = self._run_case(binary, sft.SAVE_FORMAT_VERSION_CURRENT, stale_epoch)
            self.assertEqual(c_state, sft.SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE)

    def test_current_format_and_epoch_is_current_in_native_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = self._build_probe_binary(Path(tmp))
            c_state = self._run_case(binary, sft.SAVE_FORMAT_VERSION_CURRENT, self.epoch)
            self.assertEqual(c_state, sft.SAVE_COMPAT_CURRENT)



class DocsPrecedenceWordingRegressionTests(unittest.TestCase):
    """Guards docs/save_format.md's corrected "Format / compatibility bump
    table" wording against ever silently reverting to the factually wrong
    pre-review-fix claim."""

    def setUp(self):
        self.assertTrue(DOCS_PATH.exists(), f"missing doc: {DOCS_PATH}")
        self.text = DOCS_PATH.read_text(encoding="utf-8")

    def test_pre_sprint_2_row_states_migratable_older_not_config_incompatible(self):
        marker = (
            "a genuine pre-sprint-2 save (`formatVersion` `1`, `compatEpoch` `1`) "
            "classifies `SAVE_COMPAT_MIGRATABLE_OLDER`"
        )
        self.assertIn(
            marker, self.text,
            "docs/save_format.md's bump table must document the real "
            "classifier precedence (formatVersion checked before "
            "compatEpoch) for a genuine pre-sprint-2 save",
        )

    def test_pre_sprint_2_row_no_longer_claims_config_incompatible(self):
        wrong_claim = (
            "a genuine pre-sprint-2 save classifies "
            "`SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE` and must go through the "
            "host `migrate` CLI"
        )
        self.assertNotIn(
            wrong_claim, self.text,
            "docs/save_format.md must not reintroduce the factually wrong "
            "pre-review-fix claim that a genuine pre-sprint-2 save "
            "classifies SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE",
        )


if __name__ == "__main__":
    unittest.main()
