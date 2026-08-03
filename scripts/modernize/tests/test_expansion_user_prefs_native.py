"""Byte-exact, matrix proof for struct ExpansionUserPrefs's classification
and normalization contract (issue #18 sprint 2).

Mirrors scripts/modernize/tests/test_save_format_meta_bytes_native.py's own
pattern exactly: extracts the *real* struct/function definitions verbatim
from include/expansion_save_prefs.h and src/bmsave-lib.c (never a
hand-retyped copy), assembles them into a small host-native (not
agbcc/ARM) C program, actually compiles and *executes* it against a fixed
matrix of raw 12-byte records, and compares the C side's classification/
normalization output against scripts/modernize/save_format_tool.py's
already byte-exact Python mirror for the exact same inputs.

Matrix covered (see include/expansion_save_prefs.h's enum
ExpansionUserPrefsState for the full precedence rationale):

* blank SRAM (all 0xFF)                    -> UNSET
* never-written/legacy pre-sprint-2 (all 0x00) -> UNSET
* a well-formed, current, enabled record    -> VALID
* an unknown localeId (>= locale count)     -> UNKNOWN_LOCALE
* a supported but disabled localeId         -> DISABLED_LOCALE
* a bad magic byte                          -> CORRUPT
* a bad checksum (magic/version untouched)  -> CORRUPT
* a version newer than this build knows     -> CORRUPT
* a well-formed *older* version record      -> MIGRATED

Every state also has its ExpansionUserPrefs_Normalize() output checked:
VALID/MIGRATED must yield (storedLocaleId, requiresPrompt=false); every
other state must yield (defaultLocaleId, requiresPrompt=true) -- the
"never silently trust an unusable record" no-wipe/re-prompt contract.
"""

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

from test_save_format_meta_bytes_native import (  # noqa: E402
    _extract_c_function,
    _extract_struct_with_trailing_attribute,
)


LOCALE_COUNT = 8  # mirrors EXPANSION_LOCALE_COUNT (include/expansion_locale.h)
ENABLED_MASK = 0x1  # only locale 0 ("en") enabled -- locale 1 is a supported-but-disabled probe target
DEFAULT_LOCALE_ID = 0


class ExpansionUserPrefsNativeMatrixTests(unittest.TestCase):
    """Compiles+runs the real C ExpansionUserPrefs_ValidateRaw()/
    ExpansionUserPrefs_Normalize() natively and compares their output,
    across a fixed matrix of raw records, to the Python mirror's output
    for the exact same inputs and locale context."""

    @classmethod
    def setUpClass(cls):
        cc = "cc"
        try:
            subprocess.run([cc, "--version"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, check=True)
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest("no host 'cc' compiler available")
        cls.cc = cc

        cls.bmsave_lib_c = (ROOT / "src" / "bmsave-lib.c").read_text(encoding="utf-8")
        cls.expansion_save_prefs_h = (
            ROOT / "include" / "expansion_save_prefs.h"
        ).read_text(encoding="utf-8")

    def _build_probe_binary(self, tmp_path: Path) -> Path:
        struct_def = _extract_struct_with_trailing_attribute(
            self.expansion_save_prefs_h, "ExpansionUserPrefs"
        )
        checksum16_fn = _extract_c_function(self.bmsave_lib_c, "Checksum16")
        build_fn = _extract_c_function(self.bmsave_lib_c, "ExpansionUserPrefs_Build")
        checksum_fn = _extract_c_function(self.bmsave_lib_c, "ExpansionUserPrefsChecksum")
        validate_raw_fn = _extract_c_function(self.bmsave_lib_c, "ExpansionUserPrefs_ValidateRaw")
        normalize_fn = _extract_c_function(self.bmsave_lib_c, "ExpansionUserPrefs_Normalize")

        probe_source = f"""\
#include <stdint.h>
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

#define ALIGN(m) __attribute__((aligned (m)))

typedef u8 ExpansionLocaleId;
#define EXPANSION_USER_PREFS_MAGIC 0xA5u
#define EXPANSION_USER_PREFS_VERSION_CURRENT 1u
#define EXPANSION_USER_PREFS_FLAG_LOCALE_EXPLICIT 0x01u
#define EXPANSION_USER_PREFS_SIZE_FOR_CHECKSUM 0x08
#define EXPANSION_USER_PREFS_META_OFFSET 0

#define EXPANSION_LOCALE_COUNT {LOCALE_COUNT}
#define FE8_EXPANSION_ENABLED_LOCALE_MASK {ENABLED_MASK}u
#define FE8_EXPANSION_DEFAULT_LOCALE_ID {DEFAULT_LOCALE_ID}

{struct_def};

enum ExpansionUserPrefsState {{
    EXPANSION_USER_PREFS_UNSET,
    EXPANSION_USER_PREFS_CORRUPT,
    EXPANSION_USER_PREFS_UNKNOWN_LOCALE,
    EXPANSION_USER_PREFS_DISABLED_LOCALE,
    EXPANSION_USER_PREFS_MIGRATED,
    EXPANSION_USER_PREFS_VALID
}};

{checksum16_fn}

{checksum_fn}

{build_fn}

{validate_raw_fn}

{normalize_fn}

static const char *StateName(enum ExpansionUserPrefsState state)
{{
    switch (state) {{
    case EXPANSION_USER_PREFS_UNSET: return "EXPANSION_USER_PREFS_UNSET";
    case EXPANSION_USER_PREFS_CORRUPT: return "EXPANSION_USER_PREFS_CORRUPT";
    case EXPANSION_USER_PREFS_UNKNOWN_LOCALE: return "EXPANSION_USER_PREFS_UNKNOWN_LOCALE";
    case EXPANSION_USER_PREFS_DISABLED_LOCALE: return "EXPANSION_USER_PREFS_DISABLED_LOCALE";
    case EXPANSION_USER_PREFS_MIGRATED: return "EXPANSION_USER_PREFS_MIGRATED";
    case EXPANSION_USER_PREFS_VALID: return "EXPANSION_USER_PREFS_VALID";
    }}
    return "?";
}}

int main(void)
{{
    /* Reads exactly sizeof(struct ExpansionUserPrefs) raw bytes from
     * stdin (one matrix case at a time, fed by the Python harness
     * below), plus one byte for region_unset (0/1), classifies and
     * normalizes it, and prints "state locale_id requires_prompt". */
    struct ExpansionUserPrefs prefs;
    unsigned char region_unset_byte;
    enum ExpansionUserPrefsState state;
    ExpansionLocaleId outLocaleId;
    bool8 outRequiresPrompt;

    if (fread(&prefs, sizeof(prefs), 1, stdin) != 1)
        return 2;
    if (fread(&region_unset_byte, 1, 1, stdin) != 1)
        return 2;

    state = ExpansionUserPrefs_ValidateRaw(&prefs, (bool8)region_unset_byte);
    ExpansionUserPrefs_Normalize(&prefs, state, &outLocaleId, &outRequiresPrompt);

    printf("%s %d %d\\n", StateName(state), (int)outLocaleId, (int)outRequiresPrompt);
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
            f"native user-prefs probe failed to compile:\n{compile_result.stdout}\n\n"
            f"--- generated source ---\n{probe_source}",
        )
        return binary

    def _run_case(self, binary: Path, raw12: bytes, region_unset: bool):
        self.assertEqual(len(raw12), sft.EXPANSION_USER_PREFS_SIZE)
        stdin_bytes = raw12 + bytes([1 if region_unset else 0])
        result = subprocess.run(
            [str(binary)], input=stdin_bytes,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        self.assertEqual(result.returncode, 0, f"probe crashed: {result.stdout!r}")
        parts = result.stdout.decode("ascii").strip().split()
        self.assertEqual(len(parts), 3, f"unexpected probe output: {result.stdout!r}")
        return parts[0], int(parts[1]), bool(int(parts[2]))

    def test_full_state_matrix_matches_python_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = self._build_probe_binary(Path(tmp))

            def make_raw(magic=sft.EXPANSION_USER_PREFS_MAGIC, version=sft.EXPANSION_USER_PREFS_VERSION_CURRENT,
                         locale_id=0, flags=0, reserved=b"\x00" * 4, checksum=None, fixup_checksum=True):
                prefs = sft.ExpansionUserPrefs(
                    magic=magic, version=version, locale_id=locale_id, flags=flags,
                    reserved=reserved, checksum=0 if checksum is None else checksum,
                )
                if checksum is None and fixup_checksum:
                    prefs.checksum = prefs.computed_checksum()
                return prefs

            cases = []

            # 1. blank SRAM (all 0xFF) -> UNSET
            cases.append(("blank_0xFF", bytes([0xFF] * sft.EXPANSION_USER_PREFS_SIZE), True,
                          sft.ExpansionUserPrefs.unpack(bytes([0xFF] * sft.EXPANSION_USER_PREFS_SIZE))))

            # 2. never-written/legacy pre-sprint-2 (all 0x00) -> UNSET
            cases.append(("unset_zero", bytes(sft.EXPANSION_USER_PREFS_SIZE), True,
                          sft.ExpansionUserPrefs.unpack(bytes(sft.EXPANSION_USER_PREFS_SIZE))))

            # 3. well-formed current, enabled -> VALID
            valid_prefs = make_raw(locale_id=0)
            cases.append(("valid_current_enabled", valid_prefs.pack(), False, valid_prefs))

            # 4. unknown locale id (>= LOCALE_COUNT) -> UNKNOWN_LOCALE
            unknown_prefs = make_raw(locale_id=LOCALE_COUNT + 3)
            cases.append(("unknown_locale", unknown_prefs.pack(), False, unknown_prefs))

            # 5. supported but disabled locale id (1 is not in ENABLED_MASK) -> DISABLED_LOCALE
            disabled_prefs = make_raw(locale_id=1)
            cases.append(("disabled_locale", disabled_prefs.pack(), False, disabled_prefs))

            # 6. bad magic -> CORRUPT
            bad_magic_prefs = make_raw(magic=0x00)
            cases.append(("corrupt_magic", bad_magic_prefs.pack(), False, bad_magic_prefs))

            # 7. bad checksum (magic/version untouched) -> CORRUPT
            bad_checksum_prefs = make_raw(checksum=0, fixup_checksum=False)
            # magic/version left correct, checksum deliberately wrong (0
            # does not match the real computed checksum for these fields).
            cases.append(("corrupt_checksum", bad_checksum_prefs.pack(), False, bad_checksum_prefs))

            # 8. version newer than this build knows -> CORRUPT
            newer_prefs = make_raw(version=sft.EXPANSION_USER_PREFS_VERSION_CURRENT + 1)
            cases.append(("corrupt_newer_version", newer_prefs.pack(), False, newer_prefs))

            # 9. well-formed *older* version, enabled locale -> MIGRATED
            #    (version 0 is "older than current" for this probe -- no
            #    real prior version has shipped yet, but the classifier's
            #    `<` comparison is exercised identically either way).
            older_prefs = make_raw(version=0, locale_id=0)
            cases.append(("migrated_older_version", older_prefs.pack(), False, older_prefs))

            for name, raw, region_unset, py_prefs in cases:
                with self.subTest(case=name):
                    c_state, c_locale_id, c_requires_prompt = self._run_case(binary, raw, region_unset)

                    py_state = sft.classify_user_prefs_raw(py_prefs, region_unset, LOCALE_COUNT, ENABLED_MASK)
                    py_locale_id, py_requires_prompt = sft.normalize_user_prefs(
                        py_prefs, py_state, DEFAULT_LOCALE_ID
                    )

                    self.assertEqual(c_state, py_state, f"{name}: state mismatch")
                    self.assertEqual(c_locale_id, py_locale_id, f"{name}: normalized locale id mismatch")
                    self.assertEqual(c_requires_prompt, py_requires_prompt, f"{name}: requires_prompt mismatch")


if __name__ == "__main__":
    unittest.main()
