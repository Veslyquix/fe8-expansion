"""Byte-exact proof that struct ExpansionSaveMeta's checksummed padding is
deterministically zeroed (issue #2 slice 1, review fix #3).

`BuildCurrentExpansionSaveMeta()` (src/bmsave-lib.c) previously populated
only the named fields, leaving every `STRUCT_PAD()` alignment byte inside
`EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM`'s checksum domain holding whatever
was already on the stack -- making the checksummed bytes (and therefore
the whole metadata record) non-deterministic across builds/calls. The fix
zeroes the entire struct with `memset()` before setting any field.

This module extracts the *real* function/struct definitions verbatim from
src/bmsave-lib.c, src/bmlib.c, and include/save_format.h (not a
hand-retyped copy -- so this test automatically tracks any future edit to
the real source instead of silently drifting out of sync), assembles them
into a small host-native (not agbcc/ARM) C program, actually compiles and
*executes* it with the host's own `cc`, and compares the raw bytes it
produces -- including every pad/reserved byte -- against
scripts/modernize/save_format_tool.py's already byte-exact
struct.Struct(...) packing for the same input field values. The probe is
run twice to prove the output is bit-for-bit repeatable (the specific
property the uninitialized-padding bug violated).
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))

import save_format_tool as sft  # noqa: E402


def _extract_c_function(text: str, name: str) -> str:
    """Extracts one C function's full definition (signature through its
    matching top-level closing brace) verbatim from `text`, by locating
    `name(` and then brace-counting -- robust to nested blocks, unlike a
    naive non-greedy regex."""
    decl_match = re.search(r"\n[\w][^\n;]*\b" + re.escape(name) + r"\s*\(", text)
    if decl_match is None:
        raise AssertionError(f"could not locate a definition of {name!r}")

    start = decl_match.start() + 1  # skip the leading \n
    brace_open = text.index("{", decl_match.end())

    depth = 0
    i = brace_open
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1

    raise AssertionError(f"unbalanced braces while extracting {name!r}")


def _extract_struct(text: str, name: str) -> str:
    decl_match = re.search(r"\nstruct " + re.escape(name) + r"\s*\{", text)
    if decl_match is None:
        raise AssertionError(f"could not locate struct {name!r}")
    start = decl_match.start() + 1
    end = text.index("};", decl_match.end()) + 2
    return text[start:end]


def _extract_struct_with_trailing_attribute(text: str, name: str) -> str:
    """Like _extract_struct(), but brace-depth-counts to the matching
    closing brace and then to the *next* terminating ';' after it --
    robust to a trailing attribute between the closing brace and the
    semicolon (e.g. ``} ALIGN(4);``, struct ExpansionUserPrefs's own
    closing line, include/expansion_save_prefs.h), which
    _extract_struct()'s literal ``"};"`` search cannot match."""
    decl_match = re.search(r"\nstruct " + re.escape(name) + r"\s*\{", text)
    if decl_match is None:
        raise AssertionError(f"could not locate struct {name!r}")
    start = decl_match.start() + 1
    brace_open = text.index("{", decl_match.end() - 1)

    depth = 0
    i = brace_open
    close_brace = None
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                close_brace = i
                break
        i += 1
    if close_brace is None:
        raise AssertionError(f"unbalanced braces while extracting struct {name!r}")

    end = text.index(";", close_brace) + 1
    return text[start:end]


class BuildCurrentExpansionSaveMetaNativeByteTests(unittest.TestCase):
    """Compiles+runs the real C BuildCurrentExpansionSaveMeta() natively
    (host cc, not agbcc/ARM) and compares its raw output bytes -- pad
    bytes included -- to the Python mirror's struct.pack() for the same
    controlled inputs."""

    @classmethod
    def setUpClass(cls):
        cc = "cc"
        try:
            subprocess.run([cc, "--version"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, check=True)
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest("no host 'cc' compiler available")
        cls.cc = cc

        cls.save_format_h = (ROOT / "include" / "save_format.h").read_text(encoding="utf-8")
        cls.bmsave_lib_c = (ROOT / "src" / "bmsave-lib.c").read_text(encoding="utf-8")
        cls.bmlib_c = (ROOT / "src" / "bmlib.c").read_text(encoding="utf-8")
        cls.expansion_save_prefs_h = (
            ROOT / "include" / "expansion_save_prefs.h"
        ).read_text(encoding="utf-8")

    def _build_and_run_probe(self, defines):
        """Assembles the real struct + real function bodies (extracted
        verbatim above) into a standalone, host-compilable C program,
        compiles it with the given -D overrides for the FE8_EXPANSION_*
        diagnostic macros, executes it, and returns the raw stdout bytes
        (the 0x5C-byte ExpansionSaveMeta record)."""
        struct_def = _extract_struct(self.save_format_h, "ExpansionSaveMeta")
        string_compare_fn = _extract_c_function(self.bmlib_c, "StringCompare")
        checksum16_fn = _extract_c_function(self.bmsave_lib_c, "Checksum16")
        copy_string_bounded_fn = _extract_c_function(self.bmsave_lib_c, "CopyStringBounded")
        build_meta_fn = _extract_c_function(self.bmsave_lib_c, "BuildCurrentExpansionSaveMeta")
        checksum_fn = _extract_c_function(self.bmsave_lib_c, "ExpansionSaveMetaChecksum")

        # Issue #18 sprint 2: BuildCurrentExpansionSaveMeta() now also
        # stamps a default struct ExpansionUserPrefs record into
        # `reserved` -- extract that struct/its two pure functions
        # verbatim too, so this probe keeps exercising the *real* C
        # source rather than a stale pre-sprint-2 snapshot of it.
        user_prefs_struct_def = _extract_struct_with_trailing_attribute(
            self.expansion_save_prefs_h, "ExpansionUserPrefs"
        )
        user_prefs_build_fn = _extract_c_function(self.bmsave_lib_c, "ExpansionUserPrefs_Build")
        user_prefs_checksum_fn = _extract_c_function(self.bmsave_lib_c, "ExpansionUserPrefsChecksum")

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

#define STRUCT_PAD(from, to) unsigned char _pad_ ## from[(to) - (from)]
#define ALIGN(m) __attribute__((aligned (m)))

#define EXPANSION_SAVE_META_MAGIC "FSAV"
#define EXPANSION_SAVE_META_MAGIC_SIZE 4
#define SAVE_FORMAT_VERSION_CURRENT 2
#define EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM 0x2E

enum SaveAbiId {{
    SAVE_ABI_ID_APCS_GNU = 0,
    SAVE_ABI_ID_AAPCS = 1
}};

{struct_def};

/* Issue #18 sprint 2: ExpansionUserPrefs's own type/macros -- kept
 * minimal/self-contained here (rather than including the real
 * include/expansion_locale.h, which pulls in a much larger
 * message-registry surface this probe has no need for); the struct and
 * functions themselves below are still extracted byte-for-byte from the
 * real source files, only these small supporting type/macro
 * declarations are hand-written. */
typedef u8 ExpansionLocaleId;
#define EXPANSION_USER_PREFS_MAGIC 0xA5u
#define EXPANSION_USER_PREFS_VERSION_CURRENT 1u
#define EXPANSION_USER_PREFS_FLAG_LOCALE_EXPLICIT 0x01u
#define EXPANSION_USER_PREFS_SIZE_FOR_CHECKSUM 0x08
#define EXPANSION_USER_PREFS_META_OFFSET 0

{user_prefs_struct_def};

#include "expansion_config.h"

{string_compare_fn}

{checksum16_fn}

{copy_string_bounded_fn}

{checksum_fn}

{user_prefs_checksum_fn}

{user_prefs_build_fn}

{build_meta_fn}

int main(void)
{{
    struct ExpansionSaveMeta meta;
    BuildCurrentExpansionSaveMeta(&meta);
    fwrite(&meta, sizeof(meta), 1, stdout);
    return 0;
}}
"""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "probe.c"
            binary = tmp_path / "probe"
            source.write_text(probe_source, encoding="utf-8")

            compile_cmd = [
                self.cc,
                "-iquote", str(ROOT / "include"),
                "-std=c99",
                *defines,
                str(source), "-o", str(binary),
            ]
            compile_result = subprocess.run(
                compile_cmd, cwd=ROOT, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(
                compile_result.returncode, 0,
                f"native probe failed to compile:\n{compile_result.stdout}\n\n"
                f"--- generated source ---\n{probe_source}",
            )

            run_result = subprocess.run(
                [str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(run_result.returncode, 0, "native probe crashed")
            return run_result.stdout

    def test_native_c_output_matches_python_pack_byte_for_byte(self):
        defines = [
            "-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=42",
            "-DFE8_EXPANSION_ABI=\"aapcs\"",
            "-DFE8_EXPANSION_VERSION_PACKED=0x010203u",
            "-DFE8_EXPANSION_CONFIG_FINGERPRINT=\"1234567890abcdef\"",
            "-DFE8_EXPANSION_BUILD_COMMIT=\"deadbeefcafebabe1234\"",
        ]
        c_bytes = self._build_and_run_probe(defines)

        # Issue #18 sprint 2: the C probe stamps a default
        # ExpansionUserPrefs record (locale id 0 -- the -D flags above
        # never override FE8_EXPANSION_DEFAULT_LOCALE_ID, so
        # include/expansion_config.h's own fallback default (0) applies
        # on both the C and Python sides identically) into `reserved`,
        # zero-padded out to the full reserved-tail size -- no longer an
        # all-zero reserved tail.
        default_prefs = sft.build_default_user_prefs(0, explicit_selection=False)
        default_prefs_bytes = default_prefs.pack()
        expected_reserved = default_prefs_bytes + b"\x00" * (
            sft.META_SIZE - sft.META_CHECKSUM_DOMAIN - 2 - len(default_prefs_bytes)
        )

        py_meta = sft.ExpansionSaveMeta(
            magic=sft.META_MAGIC,
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT,
            compat_epoch=42,
            abi_id=sft.SAVE_ABI_ID_AAPCS,
            framework_version_packed=0x010203,
            config_fingerprint=b"1234567890abcdef\x00",
            build_commit_short=(b"deadbeefcafebabe1234"[:8] + b"\x00" * 9)[:9],
            checksum=0,
            reserved=expected_reserved,
        )
        py_meta.checksum = py_meta.computed_checksum()
        py_bytes = py_meta.pack()

        self.assertEqual(len(c_bytes), sft.META_SIZE)
        self.assertEqual(
            c_bytes, py_bytes,
            f"C probe output {c_bytes.hex()} != Python pack {py_bytes.hex()}",
        )

        # Every STRUCT_PAD() byte inside the checksum domain must be
        # exactly zero, not leftover stack garbage -- the actual bug.
        pad_offsets = [0x05, 0x09, 0x0A, 0x0B, 0x21, 0x22, 0x23, 0x2D]
        for offset in pad_offsets:
            self.assertEqual(
                c_bytes[offset], 0,
                f"pad byte at offset 0x{offset:02X} was not deterministically zeroed",
            )

        # Every byte of `reserved` past the stamped ExpansionUserPrefs
        # record (issue #18 sprint 2's remaining headroom) must also be
        # exactly zero, not leftover stack garbage -- same determinism
        # property, extended to the new sub-record's own tail.
        reserved_start = sft.META_CHECKSUM_DOMAIN + 2
        headroom_start = reserved_start + len(default_prefs_bytes)
        for offset in range(headroom_start, sft.META_SIZE):
            self.assertEqual(
                c_bytes[offset], 0,
                f"reserved headroom byte at offset 0x{offset:02X} was not deterministically zeroed",
            )

    def test_native_c_output_multi_locale_leaves_prefs_canonically_unset(self):
        """Issue #18 sprint 6 runtime blocker fix: when
        FE8_EXPANSION_ENABLED_LOCALE_MASK enables more than one locale,
        BuildCurrentExpansionSaveMeta() must leave the ExpansionUserPrefs
        sub-record fully zeroed (EXPANSION_USER_PREFS_UNSET), never
        stamp a syntactically VALID default -- a real, compiled-and-run
        proof (not just the Python-mirror-only coverage in
        test_save_format_tool.py's BuildDefaultReservedBytesForLocaleContextTests)
        that the real C `reserved` tail actually stays all-zero in this
        configuration."""
        defines = [
            "-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=42",
            "-DFE8_EXPANSION_ABI=\"aapcs\"",
            "-DFE8_EXPANSION_VERSION_PACKED=0x010203u",
            "-DFE8_EXPANSION_CONFIG_FINGERPRINT=\"1234567890abcdef\"",
            "-DFE8_EXPANSION_BUILD_COMMIT=\"deadbeefcafebabe1234\"",
            "-DFE8_EXPANSION_ENABLED_LOCALE_MASK=0x81u",  # en (bit 0) + qps-ploc (bit 7)
        ]
        c_bytes = self._build_and_run_probe(defines)

        self.assertEqual(len(c_bytes), sft.META_SIZE)

        reserved_start = sft.META_CHECKSUM_DOMAIN + 2
        reserved = c_bytes[reserved_start:reserved_start + sft.EXPANSION_SAVE_META_RESERVED_SIZE]
        self.assertEqual(
            reserved, b"\x00" * sft.EXPANSION_SAVE_META_RESERVED_SIZE,
            "multi-enabled-locale build must leave the whole reserved tail "
            "(including the ExpansionUserPrefs sub-record) canonically "
            "zeroed/UNSET, never auto-stamp a VALID default",
        )

        prefs_bytes = reserved[:sft.EXPANSION_USER_PREFS_SIZE]
        state, _prefs = sft.classify_user_prefs_bytes(prefs_bytes, 8, 0x81)
        self.assertEqual(state, sft.EXPANSION_USER_PREFS_UNSET)

    def test_native_c_output_is_repeatable_across_builds(self):
        """The exact property the bug violated: rebuilding/re-running must
        yield bit-for-bit identical output, proving no uninitialized
        stack/heap memory leaks into the checksummed record."""
        defines = [
            "-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=7",
            "-DFE8_EXPANSION_ABI=\"apcs-gnu\"",
            "-DFE8_EXPANSION_VERSION_PACKED=0x020304u",
            "-DFE8_EXPANSION_CONFIG_FINGERPRINT=\"abcdefabcdefabcd\"",
            "-DFE8_EXPANSION_BUILD_COMMIT=\"0011223344556677\"",
        ]
        first = self._build_and_run_probe(defines)
        second = self._build_and_run_probe(defines)
        third = self._build_and_run_probe(defines)
        self.assertEqual(first, second)
        self.assertEqual(second, third)
        self.assertEqual(len(first), sft.META_SIZE)


if __name__ == "__main__":
    unittest.main()
