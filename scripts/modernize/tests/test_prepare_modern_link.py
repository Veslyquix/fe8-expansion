"""Tests for the transitional modern-link generator.

Covers every transformation, fail-closed anchor checks, deduplication,
determinism, and path safety including spaces.
"""

import importlib.util
import os
import tempfile
import textwrap
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "prepare_modern_link.py"
spec = importlib.util.spec_from_file_location("prepare_modern_link", SCRIPT)
gen = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gen)

# ---------------------------------------------------------------------------
# Minimal fixture linker fragments that contain every required anchor.
# ---------------------------------------------------------------------------

_FIXTURE_LDSCRIPT = textwrap.dedent("""\
    MEMORY { rom : ORIGIN = 0x08000000, LENGTH = 32M }
    ewram_data (NOLOAD) : {
        . = ALIGN(4); src/hardware.o(ewram_data);
        . = ALIGN(4); src/proc.o(ewram_data);
        . = 0x3EFB8; gLoadUnitBuffer = .;
        . = 0x3EFB8; end = .;
    }
    IWRAM (NOLOAD) : {
        INCLUDE "sym_iwram.txt"
    }
    ROM __text_start :
    ALIGN(4)
    {
        src/rom_header.o(.text);
        src/crt0.o(.text);
        src/main.o(.text);
        src/proc.o(.text);
        *libgcc.a:_divsi3.o(.text);
        *libgcc.a:dp-bit.o(.text);
        *libgcc.a:fp-bit.o(.text);
        *libc.a:memcpy.o(.text);
        *libc.a:syscalls.o(.text);
        *libc.a:libcfunc.o(.text);
        *libc.a:s_isinf.o(.text);
        asm/arm_call.o(.text);

        /* .rodata */
        . = ALIGN(4); src/main.o(.rodata);
        . = ALIGN(4); INCLUDE "linker_script_sound.txt"
        . = ALIGN(4); *libc.a:impure.o(.rodata);
        . = ALIGN(4); *libc.a:syscalls.o(.rodata);

        /* .data */
        . = ALIGN(4); src/main.o(.data);
        . = ALIGN(4); src/proc.o(.data);
        . = ALIGN(4); *libc.a:impure.o(.data);
        FILL(0xFF);
        . = 0xC00000; src/banim_data.o(.data.banim_array_len);
        . = 0xFFF000; src/data/data_FFF000.o(.data);
    } = 0
    /DISCARD/ : { *(*); }
""")

_FIXTURE_IWRAM = textwrap.dedent("""\
    . = ALIGN(4); src/rng.o(.bss);
    . = 0x001DA0; gText_GoldBox = .;
    . = 0x001DA8; gUnk_59 = .;
    . = 0x002A68;
    . = ALIGN(4); src/agb_sram.o(.bss);
    . = ALIGN(4); *libc.a:syscalls.o(.bss);
    . = ALIGN(4); *libgcc.a:dp-bit.o(.bss);
    . = ALIGN(4); *libgcc.a:fp-bit.o(.bss);
    . = 0x002C60; SoundMainRAM_Buffer = .;
    . = 0x002C61; gUnk_62 = .;
    . = 0x003070; gOamLoPutIt = .;
    . = 0x005410; gSoundInfo = .;
    . = 0x006480; gMPlayJumpTable = .;
    . = 0x006484; gUnk_84 = .;
    . = 0x006508; gUnk_85 = .;
    . = 0x00650C; gUnk_86 = .;
    . = 0x006510; gCgbChans = .;
    . = 0x006710; gMPlayMemAccArea = .;
    . = 0x0067A0; ReadSramFast = .;
    . = 0x0067A4; VerifySramFast = .;
    . = ALIGN(4); *libc.a:sbrkr.o(COMMON);
""")

_FIXTURE_SOUND = textwrap.dedent("""\
    src/m4a_tables.o(.rodata);
    sound/voicegroups/voicegroup000.o(.rodata);
""")


class PrepareModernLinkTests(unittest.TestCase):

    def _make_repo(self, root: Path) -> None:
        """Write fixture files into a temporary repository-like tree."""
        (root / "ldscript.txt").write_text(_FIXTURE_LDSCRIPT, encoding="utf-8")
        (root / "sym_iwram.txt").write_text(_FIXTURE_IWRAM, encoding="utf-8")
        (root / "linker_script_sound.txt").write_text(
            _FIXTURE_SOUND, encoding="utf-8"
        )

    def _make_manifest(self, root: Path, entries: list[str]) -> Path:
        manifest = root / "manifest.txt"
        manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")
        return manifest

    # -- Object substitution ------------------------------------------------

    def test_object_substitution_replaces_manifest_entries(self):
        manifest = {"src/main.o", "src/proc.o", "asm/arm_call.o"}
        result = gen._substitute_objects(
            "src/main.o(.text); src/crt0.o(.text); asm/arm_call.o(.text);",
            manifest,
            "build/mod",
        )
        self.assertIn("build/mod/src/main.o(.text)", result)
        self.assertIn("src/crt0.o(.text)", result)
        self.assertIn("build/mod/asm/arm_call.o(.text)", result)

    def test_object_substitution_ignores_non_manifest(self):
        result = gen._substitute_objects(
            "src/unknown.o(.text);", {"src/main.o"}, "build/mod"
        )
        self.assertEqual(result, "src/unknown.o(.text);")

    def test_no_substring_replacement(self):
        """src/main.o must not match suffixed variants."""
        text = (
            "src/main.o.bak src/main.obj src/main.o-bak"
            " src/main.o+x src/main.o/p src/main.o(.text)"
        )
        result = gen._substitute_objects(text, {"src/main.o"}, "build/mod")
        self.assertEqual(
            result,
            "src/main.o.bak src/main.obj src/main.o-bak"
            " src/main.o+x src/main.o/p"
            " build/mod/src/main.o(.text)",
        )

    def test_substitution_quotes_paths_with_spaces(self):
        result = gen._substitute_objects(
            "src/main.o(.text);", {"src/main.o"}, "build dir/mod"
        )
        self.assertEqual(result, '"build dir/mod/src/main.o"(.text);')

    def test_substitution_rejects_embedded_quotes(self):
        with self.assertRaises(ValueError):
            gen._substitute_objects(
                "src/main.o(.text);", {"src/main.o"}, 'build"dir/mod'
            )

    # -- Library transforms -------------------------------------------------

    def test_libc_member_renamed(self):
        result = gen._map_libc_member("*libc.a:memcpy.o(.text)")
        self.assertEqual(result, "*libc.a:libc_a-memcpy.o(.text)")

    def test_libc_syscalls_removed(self):
        result = gen._map_libc_member("*libc.a:syscalls.o(.text)")
        self.assertIn("removed", result)
        self.assertNotIn("libc_a-", result)

    def test_libc_libcfunc_removed(self):
        result = gen._map_libc_member("*libc.a:libcfunc.o(.text)")
        self.assertIn("removed", result)

    def test_libc_s_isinf_moved_to_libm(self):
        result = gen._map_libc_member("*libc.a:s_isinf.o(.text)")
        self.assertEqual(result, "*libm.a:libm_a-s_isinf.o(.text)")

    def test_libgcc_dpbit_removed(self):
        result = gen._remove_obsolete_libgcc(
            "        *libgcc.a:dp-bit.o(.text);\n"
            "        *libgcc.a:fp-bit.o(.bss);\n"
            "        *libgcc.a:_divsi3.o(.text);\n"
        )
        self.assertNotIn("dp-bit", result)
        self.assertNotIn("fp-bit", result)
        self.assertIn("_divsi3", result)

    def test_lib_section_widened(self):
        result = gen._widen_lib_sections("*libgcc.a:_divsi3.o(.text)")
        self.assertEqual(result, "*libgcc.a:_divsi3.o(.text .text.*)")

    def test_lib_rodata_section_widened(self):
        result = gen._widen_lib_sections("*libc.a:libc_a-impure.o(.rodata)")
        self.assertEqual(result, "*libc.a:libc_a-impure.o(.rodata .rodata.*)")

    # -- EWRAM pin relaxation -----------------------------------------------

    def test_ewram_pins_relaxed(self):
        text = (
            "        . = 0x3EFB8; gLoadUnitBuffer = .;\n"
            "        . = 0x3EFB8; end = .;\n"
        )
        result = gen._relax_ewram_pins(text)
        self.assertNotIn("0x3EFB8", result)
        self.assertIn("gLoadUnitBuffer = .;", result)
        self.assertIn("end = .;", result)
        self.assertIn("transitional", result)

    # -- Anchor validation --------------------------------------------------

    def test_missing_anchor_raises(self):
        with self.assertRaises(ValueError) as ctx:
            gen._check_anchor("no anchor here", "MISSING", "test anchor")
        self.assertIn("0 times", str(ctx.exception))

    def test_duplicate_anchor_raises(self):
        with self.assertRaises(ValueError) as ctx:
            gen._check_anchor("XX XX", "XX", "test anchor")
        self.assertIn("2 times", str(ctx.exception))

    # -- Catchalls ----------------------------------------------------------

    def test_catchalls_inserted_at_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_repo(root)
            manifest = {"src/main.o", "src/proc.o", "asm/arm_call.o"}
            result = gen.transform_ldscript(
                _FIXTURE_LDSCRIPT, manifest, "build/mod", str(root / "out")
            )

        self.assertIn("*(.text .text.* .glue_7 .glue_7t)", result)
        self.assertIn("*(.rodata .rodata.*", result)
        self.assertIn("*(.data .data.* .text .text.* .rodata .rodata.*)", result)
        self.assertIn(".bss.catchall", result)
        self.assertIn("*(ewram_data)", result)

    def test_catchalls_fail_on_missing_anchor(self):
        """A ldscript without the arm_call anchor must fail."""
        broken = _FIXTURE_LDSCRIPT.replace("asm/arm_call.o(.text);", "")
        with self.assertRaises(ValueError):
            gen.transform_ldscript(broken, set(), "build/mod", "out")

    # -- Include redirection ------------------------------------------------

    def test_includes_redirected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_repo(root)
            result = gen.transform_ldscript(
                _FIXTURE_LDSCRIPT, set(), "build/mod", "out/link"
            )

        self.assertIn('INCLUDE "out/link/sym_iwram.ld"', result)
        self.assertIn('INCLUDE "out/link/linker_script_sound.ld"', result)
        self.assertNotIn('INCLUDE "sym_iwram.txt"', result)
        self.assertNotIn('INCLUDE "linker_script_sound.txt"', result)

    def test_include_redirect_fails_on_missing_iwram(self):
        broken = _FIXTURE_LDSCRIPT.replace('INCLUDE "sym_iwram.txt"', "")
        with self.assertRaises(ValueError) as ctx:
            gen.transform_ldscript(broken, set(), "build/mod", "out")
        self.assertIn("INCLUDE sym_iwram", str(ctx.exception))

    def test_include_redirect_fails_on_missing_sound(self):
        broken = _FIXTURE_LDSCRIPT.replace('INCLUDE "linker_script_sound.txt"', "")
        with self.assertRaises(ValueError) as ctx:
            gen.transform_ldscript(broken, set(), "build/mod", "out")
        self.assertIn("INCLUDE linker_script_sound", str(ctx.exception))

    def test_include_redirect_fails_on_duplicate(self):
        doubled = _FIXTURE_LDSCRIPT + '\n        INCLUDE "sym_iwram.txt"\n'
        with self.assertRaises(ValueError) as ctx:
            gen.transform_ldscript(doubled, set(), "build/mod", "out")
        self.assertIn("2 times", str(ctx.exception))

    def test_include_redirect_rejects_embedded_quote_in_output_dir(self):
        with self.assertRaises(ValueError):
            gen.transform_ldscript(_FIXTURE_LDSCRIPT, set(), "build/mod", 'out"dir')

    def test_include_redirect_rejects_embedded_newline_in_output_dir(self):
        with self.assertRaises(ValueError):
            gen.transform_ldscript(_FIXTURE_LDSCRIPT, set(), "build/mod", "out\ndir")

    # -- Include fragment transforms ----------------------------------------

    def test_iwram_fragment_transformed(self):
        manifest = {"src/rng.o"}
        result = gen.transform_include(_FIXTURE_IWRAM, manifest, "build/mod")
        self.assertIn("build/mod/src/rng.o(.bss)", result)
        self.assertNotIn("dp-bit", result)
        self.assertNotIn("fp-bit", result)
        self.assertIn("removed: libc syscalls.o", result)
        self.assertIn("libc_a-sbrkr.o", result)

    def test_all_eight_iwram_placements_restored(self):
        manifest = {"src/rng.o", "src/agb_sram.o", "src/bmshop.o", "src/m4a.o"}
        result = gen.transform_iwram_include(_FIXTURE_IWRAM, manifest, "build/mod")

        expected_sections = {
            "gText_GoldBox": "build/mod/src/bmshop.o(.bss.gText_GoldBox)",
            "SoundMainRAM_Buffer": "build/mod/src/m4a.o(.bss.code)",
            "gSoundInfo": "build/mod/src/m4a.o(.bss.gSoundInfo)",
            "gMPlayJumpTable": "build/mod/src/m4a.o(.bss.gMPlayJumpTable)",
            "gCgbChans": "build/mod/src/m4a.o(.bss.gCgbChans)",
            "gMPlayMemAccArea": "build/mod/src/m4a.o(.bss.gMPlayMemAccArea)",
            "ReadSramFast": "build/mod/src/agb_sram.o(.bss.ReadSramFast)",
            "VerifySramFast": "build/mod/src/agb_sram.o(.bss.VerifySramFast)",
        }

        for symbol, selector in expected_sections.items():
            self.assertIn(selector, result, symbol)
            self.assertNotIn(f"{symbol} = .;", result)

    def test_legitimate_pins_preserved(self):
        result = gen.transform_iwram_include(
            _FIXTURE_IWRAM,
            {"src/rng.o", "src/agb_sram.o", "src/bmshop.o", "src/m4a.o"},
            "build/mod",
        )
        self.assertIn(". = 0x001DA8; gUnk_59 = .;", result)
        self.assertIn(". = 0x003070; gOamLoPutIt = .;", result)

    def test_aliases_converted_to_absolute(self):
        result = gen.transform_iwram_include(
            _FIXTURE_IWRAM,
            {"src/rng.o", "src/agb_sram.o", "src/bmshop.o", "src/m4a.o"},
            "build/mod",
        )
        self.assertIn("PROVIDE(gUnk_62 = __iwram_start + 0x002C61);", result)
        self.assertIn("PROVIDE(gUnk_84 = __iwram_start + 0x006484);", result)
        self.assertIn("PROVIDE(gUnk_85 = __iwram_start + 0x006508);", result)
        self.assertIn("PROVIDE(gUnk_86 = __iwram_start + 0x00650C);", result)

    def test_agbsram_bss_replaced_with_work_sections(self):
        result = gen.transform_iwram_include(
            _FIXTURE_IWRAM,
            {"src/rng.o", "src/agb_sram.o", "src/bmshop.o", "src/m4a.o"},
            "build/mod",
        )
        self.assertNotIn('src/agb_sram.o(.bss);', result)
        self.assertIn("build/mod/src/agb_sram.o(.bss.readSramFast_Work);", result)
        self.assertIn("build/mod/src/agb_sram.o(.bss.verifySramFast_Work);", result)
        self.assertIn("build/mod/src/agb_sram.o(.bss.verifySramValueFast_Work);", result)

    def test_iwram_pin_missing_raises(self):
        broken = _FIXTURE_IWRAM.replace(". = 0x005410; gSoundInfo = .;\n", "")
        with self.assertRaises(ValueError) as ctx:
            gen.transform_iwram_include(
                broken,
                {"src/rng.o", "src/agb_sram.o", "src/bmshop.o", "src/m4a.o"},
                "build/mod",
            )
        self.assertIn("gSoundInfo", str(ctx.exception))

    def test_iwram_pin_duplicate_raises(self):
        broken = _FIXTURE_IWRAM.replace(
            ". = 0x005410; gSoundInfo = .;\n",
            ". = 0x005410; gSoundInfo = .;\n. = 0x005410; gSoundInfo = .;\n",
        )
        with self.assertRaises(ValueError) as ctx:
            gen.transform_iwram_include(
                broken,
                {"src/rng.o", "src/agb_sram.o", "src/bmshop.o", "src/m4a.o"},
                "build/mod",
            )
        self.assertIn("found 2 times", str(ctx.exception))

    def test_iwram_missing_agb_sram_owner_raises(self):
        with self.assertRaises(ValueError) as ctx:
            gen.transform_iwram_include(
                _FIXTURE_IWRAM,
                {"src/rng.o", "src/bmshop.o", "src/m4a.o"},
                "build/mod",
            )
        self.assertIn("src/agb_sram.o", str(ctx.exception))

    def test_iwram_missing_m4a_owner_raises(self):
        with self.assertRaises(ValueError) as ctx:
            gen.transform_iwram_include(
                _FIXTURE_IWRAM,
                {"src/rng.o", "src/agb_sram.o", "src/bmshop.o"},
                "build/mod",
            )
        self.assertIn("src/m4a.o", str(ctx.exception))

    def test_iwram_missing_bmshop_owner_raises(self):
        with self.assertRaises(ValueError) as ctx:
            gen.transform_iwram_include(
                _FIXTURE_IWRAM,
                {"src/rng.o", "src/agb_sram.o", "src/m4a.o"},
                "build/mod",
            )
        self.assertIn("src/bmshop.o", str(ctx.exception))

    def test_iwram_missing_all_owners_raises(self):
        with self.assertRaises(ValueError) as ctx:
            gen.transform_iwram_include(
                _FIXTURE_IWRAM, {"src/rng.o"}, "build/mod",
            )
        self.assertIn("missing", str(ctx.exception))
        self.assertIn("src/agb_sram.o", str(ctx.exception))
        self.assertIn("src/bmshop.o", str(ctx.exception))
        self.assertIn("src/m4a.o", str(ctx.exception))

    def test_iwram_placement_deterministic(self):
        manifest = {"src/rng.o", "src/agb_sram.o", "src/bmshop.o", "src/m4a.o"}
        r1 = gen.transform_iwram_include(_FIXTURE_IWRAM, manifest, "build/mod")
        r2 = gen.transform_iwram_include(_FIXTURE_IWRAM, manifest, "build/mod")
        self.assertEqual(r1, r2)

    def test_legacy_iwram_input_unchanged(self):
        legacy = textwrap.dedent("""\
            . = ALIGN(4); src/rng.o(.bss);
            . = ALIGN(4); *libc.a:sbrkr.o(COMMON);
        """)
        result = gen.transform_include(legacy, {"src/rng.o"}, "build/mod")
        self.assertEqual(
            result,
            textwrap.dedent("""\
                . = ALIGN(4); build/mod/src/rng.o(.bss);
                . = ALIGN(4); *libc.a:libc_a-sbrkr.o(COMMON);
            """),
        )

    def test_sound_fragment_substituted(self):
        manifest = {"src/m4a_tables.o"}
        result = gen.transform_include(_FIXTURE_SOUND, manifest, "build/mod")
        self.assertIn("build/mod/src/m4a_tables.o(.rodata)", result)
        self.assertIn("sound/voicegroups/voicegroup000.o(.rodata)", result)

    # -- Object list --------------------------------------------------------

    def test_object_list_deduplicates(self):
        manifest = {"src/main.o", "src/proc.o"}
        legacy = ["src/main.o", "src/crt0.o", "sound/song.o"]
        result = gen.build_object_list(manifest, "build/mod", legacy)
        self.assertEqual(len(result), 4)
        paths = [os.path.basename(p) for p in result]
        self.assertEqual(paths.count("main.o"), 1)
        self.assertIn("build/mod/src/main.o", result)
        self.assertIn("src/crt0.o", result)

    def test_object_list_sorted_deterministic(self):
        manifest = {"src/z.o", "src/a.o", "asm/arm.o"}
        result1 = gen.build_object_list(manifest, "build/mod", ["sound/x.o"])
        result2 = gen.build_object_list(manifest, "build/mod", ["sound/x.o"])
        self.assertEqual(result1, result2)
        modern_part = [p for p in result1 if "build/mod" in p]
        self.assertEqual(modern_part, sorted(modern_part))

    def test_object_list_quotes_paths_with_spaces(self):
        result = gen.build_object_list(
            {"src/a.o"}, "build dir/mod", ["legacy obj/b.o"]
        )
        self.assertIn('"build dir/mod/src/a.o"', result)
        self.assertIn('"legacy obj/b.o"', result)

    def test_object_list_no_quotes_without_spaces(self):
        result = gen.build_object_list({"src/a.o"}, "build/mod", ["x.o"])
        for entry in result:
            self.assertNotIn('"', entry)

    def test_object_list_rejects_embedded_quote(self):
        with self.assertRaises(ValueError):
            gen.build_object_list({"src/a.o"}, 'build"mod', [])

    def test_object_list_rejects_embedded_newline(self):
        with self.assertRaises(ValueError):
            gen.build_object_list(set(), "build/mod", ["a\nb.o"])

    # -- End-to-end with path spaces ----------------------------------------

    def test_end_to_end_with_spaces_in_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo with spaces"
            root.mkdir()
            self._make_repo(root)

            mod_root = root / "build dir" / "modern"
            out_dir = root / "output dir"
            manifest_path = self._make_manifest(
                root, [
                    "src/main.o", "src/proc.o", "asm/arm_call.o",
                    "src/agb_sram.o", "src/bmshop.o", "src/m4a.o",
                ]
            )

            gen.main([
                "--root", str(root),
                "--modern-root", str(mod_root),
                "--manifest", str(manifest_path),
                "--output-dir", str(out_dir),
                "--legacy-objects", "src/crt0.o", "sound/song.o",
            ])

            self.assertTrue((out_dir / "ldscript.ld").is_file())
            self.assertTrue((out_dir / "sym_iwram.ld").is_file())
            self.assertTrue((out_dir / "linker_script_sound.ld").is_file())
            self.assertTrue((out_dir / "objects.lst").is_file())

            ld = (out_dir / "ldscript.ld").read_text(encoding="utf-8")
            self.assertIn(str(mod_root / "src" / "main.o"), ld)
            self.assertNotIn("0x3EFB8", ld)

            obj_list = (out_dir / "objects.lst").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(obj_list), 8)

    # -- Deterministic output bytes -----------------------------------------

    def test_outputs_are_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_repo(root)
            manifest = {"src/main.o", "src/proc.o"}

            r1 = gen.transform_ldscript(
                _FIXTURE_LDSCRIPT, manifest, "build/mod", "out"
            )
            r2 = gen.transform_ldscript(
                _FIXTURE_LDSCRIPT, manifest, "build/mod", "out"
            )
            self.assertEqual(r1, r2)

    # -- Full ldscript transform checks everything --------------------------

    def test_full_transform_applies_all_six_transforms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_repo(root)
            manifest = {"src/main.o", "src/proc.o", "asm/arm_call.o"}
            result = gen.transform_ldscript(
                _FIXTURE_LDSCRIPT, manifest, "bld", str(root / "out")
            )

        self.assertIn("bld/src/main.o(.text)", result)
        self.assertIn("src/crt0.o(.text)", result)
        self.assertNotIn("dp-bit", result)
        self.assertNotIn("fp-bit", result)
        self.assertIn("libc_a-memcpy.o(.text .text.*)", result)
        self.assertIn("removed: libc syscalls.o", result)
        self.assertIn("removed: libc libcfunc.o", result)
        self.assertIn("libm_a-s_isinf.o(.text .text.*)", result)
        self.assertNotIn("0x3EFB8", result)
        self.assertIn("*(.text .text.* .glue_7 .glue_7t)", result)
        self.assertIn(".bss.catchall", result)
        self.assertIn("*(ewram_data)", result)
        self.assertIn(f'INCLUDE "{root / "out" / "sym_iwram.ld"}"', result)

    # -- Real linker parse test with spaces ---------------------------------

    def test_real_ld_parses_generated_script_with_spaces(self):
        """Invoke real arm-none-eabi-ld on a generated script with spaced paths."""
        import shutil
        import subprocess

        prefix = os.environ.get("PREFIX", "arm-none-eabi-")
        ld = shutil.which(f"{prefix}ld")
        gas = shutil.which(f"{prefix}as")
        if not ld or not gas:
            self.skipTest("arm-none-eabi-as/ld not available")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "dir with spaces"
            base.mkdir()

            obj_dir = base / "modern objs"
            obj_dir.mkdir()
            out_dir = base / "link out"
            out_dir.mkdir()

            asm_src = base / "stub.s"
            asm_src.write_text(
                ".syntax unified\n.thumb\n"
                ".global _start\n_start: bx lr\n",
                encoding="utf-8",
            )
            obj_path = obj_dir / "src"
            obj_path.mkdir()
            stub_o = obj_path / "stub.o"
            subprocess.run(
                [gas, "-mcpu=arm7tdmi", "-mthumb-interwork",
                 str(asm_src), "-o", str(stub_o)],
                check=True,
            )

            manifest = out_dir / "manifest.txt"
            manifest.write_text("src/stub.o\n", encoding="utf-8")

            mini_ld = (
                'MEMORY { rom : ORIGIN = 0x08000000, LENGTH = 1M }\n'
                'ENTRY(_start)\n'
                'SECTIONS {\n'
                '    ROM : { src/stub.o(.text); } > rom\n'
                '    /DISCARD/ : { *(*); }\n'
                '}\n'
            )
            mini_ld_path = base / "mini.ld"
            mini_ld_path.write_text(mini_ld, encoding="utf-8")

            transformed = gen._substitute_objects(
                mini_ld, {"src/stub.o"}, str(obj_dir)
            )
            gen_ld = out_dir / "test.ld"
            gen_ld.write_text(transformed, encoding="utf-8")

            obj_list = gen.build_object_list(
                {"src/stub.o"}, str(obj_dir), []
            )
            lst_path = out_dir / "objects.lst"
            lst_path.write_text("\n".join(obj_list) + "\n", encoding="utf-8")

            result = subprocess.run(
                [ld, "-T", str(gen_ld), "@" + str(lst_path),
                 "-o", str(out_dir / "test.elf")],
                capture_output=True, text=True,
            )
            self.assertEqual(
                result.returncode, 0,
                f"ld failed with spaced paths:\n{result.stderr}",
            )
            self.assertTrue((out_dir / "test.elf").is_file())


if __name__ == "__main__":
    unittest.main()
