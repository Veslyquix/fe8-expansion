"""Tests for the expansion-modern-rom / expansion-modern-boot-check Make
target wiring.

Covers MODERN_OBJCOPY resolution (parallel to MODERN_LD/MODERN_OBJDUMP),
ROM header-verifier wiring (pass/fail-and-delete), boot-check preflight
(missing scenario/fingerprint, missing backend), dry-run safety, paths with
spaces, and non-interaction with the cohort/all/elf targets.

Tests using print-* and make -n run unconditionally.  Tests invoking real
cross tools or building the actual ROM/ELF skip only when the exact required
executable is absent.
"""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class ModernRomBootTargetTests(unittest.TestCase):

    def make(self, *args, cwd=None, env=None):
        run_env = dict(os.environ)
        if env:
            for key, value in env.items():
                if value is None:
                    run_env.pop(key, None)
                else:
                    run_env[key] = value
        return subprocess.run(
            ["make", "--no-print-directory", *args],
            cwd=cwd or ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env=run_env,
        )

    def tool_overrides(self):
        prefix = os.environ.get("PREFIX", "arm-none-eabi-")
        cc = os.environ.get("MODERN_CC", "")
        if not cc:
            root = os.environ.get("MODERN_TOOLCHAIN_ROOT", "")
            if root:
                cc = str(Path(root) / "bin" / f"{prefix}gcc")
            else:
                cc = shutil.which(f"{prefix}gcc") or ""
        objdump = os.environ.get("MODERN_OBJDUMP", "")
        if not objdump:
            objdump = shutil.which(f"{prefix}objdump") or ""
        ld = os.environ.get("MODERN_LD", "")
        if not ld:
            ld = shutil.which(f"{prefix}ld") or ""
        objcopy = os.environ.get("MODERN_OBJCOPY", "")
        if not objcopy:
            objcopy = shutil.which(f"{prefix}objcopy") or ""
        if not cc or not objdump or not ld or not objcopy:
            return None
        overrides = [
            f"MODERN_CC={cc}",
            f"MODERN_OBJDUMP={objdump}",
            f"MODERN_LD={ld}",
            f"MODERN_OBJCOPY={objcopy}",
        ]
        for var in ("MODERN_BINUTILS_DIR", "MODERN_NEWLIB_INCLUDE"):
            val = os.environ.get(var)
            if val:
                overrides.append(f"{var}={val}")
        return overrides

    # -- MODERN_OBJCOPY resolution -------------------------------------------

    def test_objcopy_defaults_to_prefix_path(self):
        """Without a toolchain root, MODERN_OBJCOPY resolves via PREFIX.
        MODERN_OBJCOPY/MODERN_TOOLCHAIN_ROOT must be genuinely *unset*
        (not merely assigned an empty string) since a command-line
        assignment, even to "", still counts as "already defined" and
        would suppress modern.mk's own `?=` default."""
        result = self.make(
            "print-MODERN_OBJCOPY", "PREFIX=arm-none-eabi-",
            env={"MODERN_TOOLCHAIN_ROOT": None, "MODERN_OBJCOPY": None},
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("arm-none-eabi-objcopy", result.stdout)

    def test_objcopy_honors_toolchain_root(self):
        """With MODERN_TOOLCHAIN_ROOT set, MODERN_OBJCOPY resolves under it,
        parallel to MODERN_LD/MODERN_OBJDUMP."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.make(
                "print-MODERN_OBJCOPY", "print-MODERN_LD",
                f"MODERN_TOOLCHAIN_ROOT={tmp}",
                "PREFIX=arm-none-eabi-",
                env={"MODERN_OBJCOPY": None, "MODERN_LD": None},
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"{tmp}/bin/arm-none-eabi-objcopy", result.stdout)
        self.assertIn(f"{tmp}/bin/arm-none-eabi-ld", result.stdout)

    def test_objcopy_override_wins(self):
        result = self.make(
            "print-MODERN_OBJCOPY", "MODERN_OBJCOPY=/custom/objcopy",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("/custom/objcopy", result.stdout)

    # -- ROM header-verifier wiring ------------------------------------------

    def test_rom_rule_deletes_output_on_verifier_failure(self):
        """A failing header verifier must delete the just-built ROM so a
        stale/invalid image is never left behind."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_elf = Path(tmp, "fireemblem8.elf")
            fake_elf.write_bytes(b"\x00" * 16)
            fake_objcopy = Path(tmp, "fake_objcopy.sh")
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                '# Emulate objcopy by writing an undersized (invalid) ROM.\n'
                'for out; do :; done\n'
                'head -c 1024 /dev/zero > "$out"\n'
            )
            fake_objcopy.chmod(0o755)
            fake_verifier = Path(tmp, "fake_verify.py")
            fake_verifier.write_text(
                "import sys\n"
                "print('fake verifier: rejecting', sys.argv[1])\n"
                "sys.exit(1)\n"
            )
            rom_path = Path(tmp, "fireemblem8.gba")
            # -o (--assume-old) pins the fake ELF as up to date so the real
            # expansion-modern-link-prepare chain (whose target also happens
            # to be $(MODERN_ELF) once overridden) never fires; only the
            # $(MODERN_ROM) recipe itself is exercised.
            result = self.make(
                "-o", str(fake_elf),
                str(rom_path),
                f"MODERN_ELF={fake_elf}",
                f"MODERN_OBJCOPY={fake_objcopy}",
                f"MODERN_ROM_HEADER_VERIFIER={fake_verifier}",
                f"MODERN_ROM={rom_path}",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse(
                rom_path.exists(),
                "invalid ROM must be deleted after verifier failure",
            )

    def test_rom_rule_keeps_output_on_verifier_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_elf = Path(tmp, "fireemblem8.elf")
            fake_elf.write_bytes(b"\x00" * 16)
            fake_objcopy = Path(tmp, "fake_objcopy.sh")
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                'for out; do :; done\n'
                'head -c 1024 /dev/zero > "$out"\n'
            )
            fake_objcopy.chmod(0o755)
            fake_verifier = Path(tmp, "fake_verify.py")
            fake_verifier.write_text(
                "import sys\n"
                "print('fake verifier: accepting', sys.argv[1])\n"
                "sys.exit(0)\n"
            )
            rom_path = Path(tmp, "fireemblem8.gba")
            result = self.make(
                "-o", str(fake_elf),
                str(rom_path),
                f"MODERN_ELF={fake_elf}",
                f"MODERN_OBJCOPY={fake_objcopy}",
                f"MODERN_ROM_HEADER_VERIFIER={fake_verifier}",
                f"MODERN_ROM={rom_path}",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(rom_path.exists())

    # -- ROM size configuration (--size wiring) --------------------------------

    def test_rom_rule_passes_default_32m_size_to_verifier(self):
        """Without MODERN_ROM_SIZE, the recipe must pass --size 32M to the
        verifier. The default was 16M until the FE8_MAPGEN chunk table (and
        the pre-existing near-full 16M budget, see reports/linker-budget)
        made that no longer enough room to build with; see
        test_rom_rule_passes_16m_size_to_verifier below for the still-
        supported explicit-opt-in-to-16M path."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_elf = Path(tmp, "fireemblem8.elf")
            fake_elf.write_bytes(b"\x00" * 16)
            fake_objcopy = Path(tmp, "fake_objcopy.sh")
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                'for out; do :; done\n'
                'head -c 1024 /dev/zero > "$out"\n'
            )
            fake_objcopy.chmod(0o755)
            argv_capture = Path(tmp, "verifier_argv.txt")
            fake_verifier = Path(tmp, "fake_verify.py")
            fake_verifier.write_text(
                "import sys\n"
                f"open(r'{argv_capture}', 'w').write(' '.join(sys.argv[1:]))\n"
                "sys.exit(0)\n"
            )
            rom_path = Path(tmp, "fireemblem8.gba")
            result = self.make(
                "-o", str(fake_elf),
                str(rom_path),
                f"MODERN_ELF={fake_elf}",
                f"MODERN_OBJCOPY={fake_objcopy}",
                f"MODERN_ROM_HEADER_VERIFIER={fake_verifier}",
                f"MODERN_ROM={rom_path}",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            argv_text = argv_capture.read_text()
            self.assertIn("--size 32M", argv_text)
            self.assertTrue(argv_text.strip().endswith(str(rom_path)))

    def test_rom_rule_passes_16m_size_to_verifier(self):
        """MODERN_ROM_SIZE=16M must still flow through to the verifier's
        --size when explicitly requested, now that it is opt-in rather than
        the default (see test_rom_rule_passes_default_32m_size_to_verifier)."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_elf = Path(tmp, "fireemblem8.elf")
            fake_elf.write_bytes(b"\x00" * 16)
            fake_objcopy = Path(tmp, "fake_objcopy.sh")
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                'for out; do :; done\n'
                'head -c 1024 /dev/zero > "$out"\n'
            )
            fake_objcopy.chmod(0o755)
            argv_capture = Path(tmp, "verifier_argv.txt")
            fake_verifier = Path(tmp, "fake_verify.py")
            fake_verifier.write_text(
                "import sys\n"
                f"open(r'{argv_capture}', 'w').write(' '.join(sys.argv[1:]))\n"
                "sys.exit(0)\n"
            )
            rom_path = Path(tmp, "fireemblem8.gba")
            result = self.make(
                "-o", str(fake_elf),
                str(rom_path),
                "MODERN_ROM_SIZE=16M",
                f"MODERN_ELF={fake_elf}",
                f"MODERN_OBJCOPY={fake_objcopy}",
                f"MODERN_ROM_HEADER_VERIFIER={fake_verifier}",
                f"MODERN_ROM={rom_path}",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            argv_text = argv_capture.read_text()
            self.assertIn("--size 16M", argv_text)
            self.assertTrue(argv_text.strip().endswith(str(rom_path)))

    def test_rom_rule_passes_32m_size_to_verifier(self):
        """MODERN_ROM_SIZE=32M must flow through to the verifier's --size,
        proving the ROM/boot pipeline no longer hardcodes 16 MiB."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_elf = Path(tmp, "fireemblem8.elf")
            fake_elf.write_bytes(b"\x00" * 16)
            fake_objcopy = Path(tmp, "fake_objcopy.sh")
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                'for out; do :; done\n'
                'head -c 1024 /dev/zero > "$out"\n'
            )
            fake_objcopy.chmod(0o755)
            argv_capture = Path(tmp, "verifier_argv.txt")
            fake_verifier = Path(tmp, "fake_verify.py")
            fake_verifier.write_text(
                "import sys\n"
                f"open(r'{argv_capture}', 'w').write(' '.join(sys.argv[1:]))\n"
                "sys.exit(0)\n"
            )
            rom_path = Path(tmp, "fireemblem8.gba")
            result = self.make(
                "-o", str(fake_elf),
                str(rom_path),
                "MODERN_ROM_SIZE=32M",
                f"MODERN_ELF={fake_elf}",
                f"MODERN_OBJCOPY={fake_objcopy}",
                f"MODERN_ROM_HEADER_VERIFIER={fake_verifier}",
                f"MODERN_ROM={rom_path}",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            argv_text = argv_capture.read_text()
            self.assertIn("--size 32M", argv_text)

    def test_rom_rule_rejects_16m_output_when_32m_requested(self):
        """Using the real verifier: an objcopy output that is only 16 MiB
        while MODERN_ROM_SIZE=32M was requested must be rejected and the
        stale ROM deleted -- proving the *configured* size is enforced,
        not a hardcoded 16 MiB constant (the bug this change fixes)."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_elf = Path(tmp, "fireemblem8.elf")
            fake_elf.write_bytes(b"\x00" * 16)
            sixteen_mib = 16 * 1024 * 1024
            fake_objcopy = Path(tmp, "fake_objcopy.sh")
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                'for out; do :; done\n'
                f'head -c {sixteen_mib} /dev/zero > "$out"\n'
            )
            fake_objcopy.chmod(0o755)
            rom_path = Path(tmp, "fireemblem8.gba")
            result = self.make(
                "-o", str(fake_elf),
                str(rom_path),
                "MODERN_ROM_SIZE=32M",
                f"MODERN_ELF={fake_elf}",
                f"MODERN_OBJCOPY={fake_objcopy}",
                f"MODERN_ROM={rom_path}",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("does not match expected", result.stdout)
            self.assertFalse(
                rom_path.exists(),
                "ROM padded to the wrong size must be deleted, not left "
                "behind as a stale invalid image",
            )

    def test_rom_rule_size_check_passes_for_genuine_32m_padded_output(self):
        """A real objcopy-style 32 MiB pad must satisfy the real verifier's
        size check under MODERN_ROM_SIZE=32M (identity/checksum still fail
        for this synthetic all-zero image, but crucially not on size)."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_elf = Path(tmp, "fireemblem8.elf")
            fake_elf.write_bytes(b"\x00" * 16)
            thirty_two_mib = 32 * 1024 * 1024
            fake_objcopy = Path(tmp, "fake_objcopy.sh")
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                'for out; do :; done\n'
                f'head -c {thirty_two_mib} /dev/zero > "$out"\n'
            )
            fake_objcopy.chmod(0o755)
            rom_path = Path(tmp, "fireemblem8.gba")
            result = self.make(
                "-o", str(fake_elf),
                str(rom_path),
                "MODERN_ROM_SIZE=32M",
                f"MODERN_ELF={fake_elf}",
                f"MODERN_OBJCOPY={fake_objcopy}",
                f"MODERN_ROM={rom_path}",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertNotIn(
                "ROM size", result.stdout,
                "size check must pass for a genuine 32 MiB image; only "
                "the header identity/checksum checks should fail here",
            )

    def test_rom_rule_rejects_unsupported_rom_size(self):
        """MODERN_ROM_SIZE values other than 16M/32M must fail fast at
        Makefile-parse time, before any recipe runs."""
        result = self.make("-n", "expansion-modern-rom", "MODERN_ROM_SIZE=64M")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Unsupported MODERN_ROM_SIZE", result.stdout)

    def test_rom_dry_run_echoes_size_flag(self):
        """make -n must echo the --size flag matching MODERN_ROM_SIZE in the
        verifier invocation, without actually running anything."""
        result = self.make("-n", "expansion-modern-rom", "MODERN_ROM_SIZE=32M")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("--size", result.stdout)
        self.assertIn("32M", result.stdout)

    # -- Boot-check preflight -------------------------------------------------

    def test_boot_preflight_fails_on_missing_scenario(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.make(
                "expansion-modern-boot-preflight",
                f"MODERN_BOOT_SCENARIO={tmp}/missing_scenario.json",
                f"MODERN_BOOT_FINGERPRINT={ROOT}/tools/gba-playtest/fingerprints/boot.json",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing boot scenario or fingerprint", result.stdout)

    def test_boot_preflight_fails_on_missing_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.make(
                "expansion-modern-boot-preflight",
                f"MODERN_BOOT_SCENARIO={ROOT}/tools/gba-playtest/scenarios/boot.json",
                f"MODERN_BOOT_FINGERPRINT={tmp}/missing_fp.json",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing boot scenario or fingerprint", result.stdout)

    def test_boot_preflight_fails_with_actionable_error_on_missing_backend(self):
        """A backend-check script that always fails must produce an
        actionable error, not a bare traceback."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_playtest = Path(tmp, "fake_playtest.py")
            fake_playtest.write_text(
                "import sys\n"
                "if sys.argv[1:2] == ['backend-check']:\n"
                "    sys.exit(1)\n"
                "sys.exit(0)\n"
            )
            result = self.make(
                "expansion-modern-boot-preflight",
                f"MODERN_BOOT_SCENARIO={ROOT}/tools/gba-playtest/scenarios/boot.json",
                f"MODERN_BOOT_FINGERPRINT={ROOT}/tools/gba-playtest/fingerprints/boot.json",
                f"MODERN_PLAYTEST={fake_playtest}",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("libmGBA playtest backend is unavailable", result.stdout)
        self.assertIn("backend-check", result.stdout)

    def test_boot_preflight_succeeds_with_stub_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_playtest = Path(tmp, "fake_playtest.py")
            fake_playtest.write_text("import sys\nsys.exit(0)\n")
            result = self.make(
                "expansion-modern-boot-preflight",
                f"MODERN_BOOT_SCENARIO={ROOT}/tools/gba-playtest/scenarios/boot.json",
                f"MODERN_BOOT_FINGERPRINT={ROOT}/tools/gba-playtest/fingerprints/boot.json",
                f"MODERN_PLAYTEST={fake_playtest}",
            )
        self.assertEqual(result.returncode, 0, result.stdout)

    # -- Dry-run safety -------------------------------------------------------

    def test_rom_dry_run_does_not_invoke_objcopy(self):
        """make -n must echo the objcopy recipe line (expected) without
        actually running it; a sentinel-writing fake objcopy proves no real
        invocation happened."""
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp, "invoked.marker")
            fake_objcopy = Path(tmp, "fake_objcopy.sh")
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                f'touch "{sentinel}"\n'
            )
            fake_objcopy.chmod(0o755)
            result = self.make(
                "-n", "expansion-modern-rom",
                f"MODERN_OBJCOPY={fake_objcopy}",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(
                sentinel.exists(),
                "dry-run must not actually execute the objcopy recipe",
            )

    def test_boot_check_dry_run_does_not_invoke_playtest(self):
        """make -n must echo the gba_playtest recipe line (expected) without
        actually running it; a sentinel-writing fake playtest script proves
        no real invocation happened."""
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp, "invoked.marker")
            fake_playtest = Path(tmp, "fake_playtest.py")
            fake_playtest.write_text(
                "import pathlib, sys\n"
                f"pathlib.Path(r'{sentinel}').write_text('invoked')\n"
                "sys.exit(0)\n"
            )
            result = self.make(
                "-n", "expansion-modern-boot-check",
                f"MODERN_PLAYTEST={fake_playtest}",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(
                sentinel.exists(),
                "dry-run must not actually execute the playtest recipe",
            )

    # -- Paths with spaces ----------------------------------------------------

    def test_rom_tool_paths_with_spaces(self):
        """Tool paths (MODERN_OBJCOPY, MODERN_ROM_HEADER_VERIFIER) containing
        spaces must work: they are only ever referenced inside quoted
        recipe-body shell commands (never as a bare Make target/prerequisite
        name), so embedded spaces are safe there -- mirroring the existing
        MODERN_ELF_BANIM_SYM/MODERN_LIBGCC_DIR space-safety convention in
        test_modern_elf.py. (A *target* name such as $(MODERN_ROM) itself
        cannot contain literal spaces -- that is a pre-existing, unrelated
        GNU Make rule-parsing limitation shared by every $(MODERN_OUTPUT_DIR)
        based target in modern.mk, e.g. $(MODERN_ELF), not something specific
        to this feature.)"""
        with tempfile.TemporaryDirectory() as tmp:
            space_dir = Path(tmp, "dir with spaces")
            space_dir.mkdir()
            fake_elf = Path(tmp, "fireemblem8.elf")
            fake_elf.write_bytes(b"\x00" * 16)
            fake_objcopy = space_dir / "fake objcopy.sh"
            fake_objcopy.write_text(
                "#!/bin/sh\n"
                'for out; do :; done\n'
                'head -c 1024 /dev/zero > "$out"\n'
            )
            fake_objcopy.chmod(0o755)
            fake_verifier = space_dir / "fake verify.py"
            fake_verifier.write_text("import sys\nsys.exit(0)\n")
            rom_path = Path(tmp, "fireemblem8.gba")
            result = self.make(
                "-o", str(fake_elf),
                str(rom_path),
                f"MODERN_ELF={fake_elf}",
                f"MODERN_OBJCOPY={fake_objcopy}",
                f"MODERN_ROM_HEADER_VERIFIER={fake_verifier}",
                f"MODERN_ROM={rom_path}",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(rom_path.exists())

    # -- Compile-settings staleness (issue #8 review finding #2) --------------

    def test_expansion_metadata_recompiles_on_identity_change_without_clean(self):
        """Regression test (issue #8 review finding #2, HIGH): changing a
        config.mk/EXPANSION_* identity value (here EXPANSION_ROM_TITLE)
        between two builds sharing the same MODERN_OUTPUT_DIR, with no
        intervening `make clean`, must force src/expansion_metadata.c to
        recompile and embed the *new* value -- not silently keep the
        previous build's stale object.

        Before the fix, FE8_EXPANSION_* values only flowed into
        MODERN_CFLAGS's -D defines (content GNU Make's dependency graph
        cannot observe); this test compiles the real
        src/expansion_metadata.c with the real modern toolchain via the
        real MODERN_ALL_C_OBJECTS pipeline (MODERN_ALL_C_SOURCES/
        MODERN_ALL_DATA_C_SOURCES/MODERN_ALL_ASM_SOURCES overridden to just
        this one source, so the test compiles quickly without linking a
        full ELF), and asserts both a real recompilation (object mtime
        strictly increases) and that the *compiled object itself* now
        embeds the new title byte-for-byte (verified with `strings` on the
        raw .o, independent of any linker/ROM-finalization step) while the
        old title is no longer embedded anywhere in it.
        """
        overrides = self.tool_overrides()
        if overrides is None:
            self.skipTest("arm-none-eabi GCC/objdump/ld/objcopy are not available")

        strings_tool = shutil.which("strings")
        if strings_tool is None:
            self.skipTest("strings(1) is not available")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            common_args = [
                f"MODERN_OUTPUT_DIR={output_dir}",
                "MODERN_ALL_C_SOURCES=src/expansion_metadata.c",
                "MODERN_ALL_DATA_C_SOURCES=",
                "MODERN_ALL_ASM_SOURCES=",
                "MODERN_CONFIG=debug",
                "MODERN_ABI=aapcs",
            ]
            metadata_object = output_dir / "src" / "expansion_metadata.o"

            first = self.make(
                "expansion-modern-all", *common_args, *overrides,
            )
            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertTrue(metadata_object.exists())
            before_mtime = metadata_object.stat().st_mtime_ns
            before_strings = subprocess.run(
                [strings_tool, str(metadata_object)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False,
            ).stdout
            self.assertIn("FIREEMBLEM2E", before_strings)

            time.sleep(1.1)

            second = self.make(
                "expansion-modern-all",
                *common_args,
                "EXPANSION_ROM_TITLE=CUSTOMTITLE1",
                *overrides,
            )
            self.assertEqual(second.returncode, 0, second.stdout)
            after_mtime = metadata_object.stat().st_mtime_ns
            self.assertGreater(
                after_mtime, before_mtime,
                "src/expansion_metadata.c must recompile when "
                "EXPANSION_ROM_TITLE changes, even without an "
                "intervening `make clean`",
            )
            after_strings = subprocess.run(
                [strings_tool, str(metadata_object)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False,
            ).stdout
            self.assertIn("CUSTOMTITLE1", after_strings)
            self.assertNotIn("FIREEMBLEM2E", after_strings)

    # -- Cohort/all/elf non-interaction ---------------------------------------

    def test_cohort_dry_run_no_rom_or_boot_check(self):
        overrides = self.tool_overrides()
        if overrides is None:
            self.skipTest("modern toolchain not available")
        result = self.make("-n", "expansion-modern-cohort", *overrides)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("fireemblem8.gba", result.stdout)
        self.assertNotIn("gba_playtest", result.stdout)

    def test_all_dry_run_no_rom_or_boot_check(self):
        overrides = self.tool_overrides()
        if overrides is None:
            self.skipTest("modern toolchain not available")
        result = self.make("-n", "expansion-modern-all", *overrides)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("fireemblem8.gba", result.stdout)
        self.assertNotIn("gba_playtest", result.stdout)

    def test_elf_dry_run_no_rom_or_boot_check(self):
        overrides = self.tool_overrides()
        if overrides is None:
            self.skipTest("modern toolchain not available")
        result = self.make("-n", "expansion-modern-elf", *overrides)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("fireemblem8.gba", result.stdout)
        self.assertNotIn("gba_playtest", result.stdout)

    # -- AAPCS guard for all linked-output goals -------------------------------
    #
    # expansion-modern-elf is the only target that actually links, but
    # expansion-modern-rom/-boot-check both transitively depend on it via
    # $(MODERN_ELF) without naming "expansion-modern-elf" literally on the
    # command line. The guard must therefore recognize the whole linked-
    # output goal set. These assertions are genuinely tool-free: the ABI
    # check is a top-level $(error ...) evaluated at Makefile-parse time,
    # before any recipe (real or dry-run) is considered, so no arm-none-eabi
    # toolchain needs to be present/discoverable for either branch.

    LINKED_GOALS = (
        "expansion-modern-elf",
        "expansion-modern-rom",
        "expansion-modern-boot-check",
    )

    def test_elf_rejects_apcs_gnu_early(self):
        result = self.make("-n", "expansion-modern-elf", "MODERN_ABI=apcs-gnu")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("expansion-modern-elf", result.stdout)
        self.assertIn("requires MODERN_ABI=aapcs", result.stdout)

    def test_rom_rejects_apcs_gnu_early(self):
        result = self.make("-n", "expansion-modern-rom", "MODERN_ABI=apcs-gnu")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("expansion-modern-rom", result.stdout)
        self.assertIn("requires MODERN_ABI=aapcs", result.stdout)

    def test_boot_check_rejects_apcs_gnu_early(self):
        result = self.make(
            "-n", "expansion-modern-boot-check", "MODERN_ABI=apcs-gnu",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("expansion-modern-boot-check", result.stdout)
        self.assertIn("requires MODERN_ABI=aapcs", result.stdout)

    def test_elf_accepts_aapcs_past_abi_check(self):
        result = self.make("-n", "expansion-modern-elf", "MODERN_ABI=aapcs")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("requires MODERN_ABI=aapcs", result.stdout)

    def test_rom_accepts_aapcs_past_abi_check(self):
        result = self.make("-n", "expansion-modern-rom", "MODERN_ABI=aapcs")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("requires MODERN_ABI=aapcs", result.stdout)

    def test_boot_check_accepts_aapcs_past_abi_check(self):
        result = self.make(
            "-n", "expansion-modern-boot-check", "MODERN_ABI=aapcs",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("requires MODERN_ABI=aapcs", result.stdout)

    # -- MODERN_GOALS / NODEP wiring -------------------------------------------

    def test_rom_and_boot_check_are_modern_goals(self):
        """expansion-modern-rom/-boot-check must be in MODERN_GOALS so that
        NODEP=1 applies to them like every other modern goal."""
        mk = (ROOT / "modern.mk").read_text(encoding="utf-8")
        goals_block = mk.split("MODERN_GOALS :=", 1)[1].split(
            "ifneq", 1
        )[0]
        self.assertIn("expansion-modern-rom", goals_block)
        self.assertIn("expansion-modern-boot-check", goals_block)

    # -- expansion-modern-clean must not pay the config-validation cost --------

    def test_clean_succeeds_with_invalid_expansion_config(self):
        """Regression test (issue #8 review finding #3, MEDIUM):
        expansion-modern-clean is a member of MODERN_GOALS, but it only
        removes build output and never compiles or embeds anything
        expansion-config-related, so an invalid EXPANSION_* override (e.g.
        an over-length title) must not block it from running. Before the
        fix, the eager config resolve/validate $(shell ...) block was gated
        on the full MODERN_GOALS list (clean included), so
        `make expansion-modern-clean EXPANSION_ROM_TITLE=<invalid>` failed
        at Makefile-parse time before any cleanup occurred.

        Runs against the real repository root (which -- unlike the
        config-less synthetic fixtures used elsewhere -- has a real
        config.mk, so MODERN_EXPANSION_CONFIG_AVAILABLE is true and the
        eager resolve block is actually reachable), but overrides
        MODERN_BUILD_ROOT to a throwaway directory so the real build/
        tree is never touched.
        """
        with tempfile.TemporaryDirectory() as temporary:
            build_root = Path(temporary) / "expansion-modern"
            marker_dir = build_root / "debug" / "aapcs"
            marker_dir.mkdir(parents=True)
            marker = marker_dir / "marker.txt"
            marker.write_text("stale build output\n", encoding="utf-8")

            result = self.make(
                "expansion-modern-clean",
                f"MODERN_BUILD_ROOT={build_root}",
                "EXPANSION_ROM_TITLE="
                "WAY_TOO_LONG_TITLE_EXCEEDING_TWELVE_BYTES",
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("EXPANSION_ROM_TITLE", result.stdout)
            self.assertFalse(build_root.exists())

    def test_clean_dry_run_does_not_validate_expansion_config(self):
        """A dry-run of expansion-modern-clean with an invalid config value
        must not even report an error (mirroring the real-run assertion
        above at Makefile-parse time, before any recipe would run)."""
        result = self.make(
            "-n",
            "expansion-modern-clean",
            "EXPANSION_ROM_GAME_CODE=TOOLONGCODE",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("EXPANSION_ROM_GAME_CODE", result.stdout)


if __name__ == "__main__":
    unittest.main()
