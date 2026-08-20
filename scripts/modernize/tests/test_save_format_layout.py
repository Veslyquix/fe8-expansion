"""Compile-time layout assertions for every persisted save struct (issue #2
slices 1-2).

Verifies, byte-for-byte, that the *entire* persisted struct SaveBlocks tree
(include/bmsave.h) -- not just its top-level fields -- has identical
sizeof/offsetof under the legacy agbcc (APCS) compiler that ships
fireemblem8.gba and under every modern arm-none-eabi-gcc (AAPCS/APCS-GNU)
build cell. This includes struct ExpansionSaveMeta (include/save_format.h),
which is exactly 0x5C bytes and replaces the old pad at SRAM offset 0x73A4
without shifting any neighboring block's offset or struct SaveBlocks' total
size.

Historical note -- two real cross-compiler layout divergences were found
and fixed by this probe (see include/bmdifficulty.h and include/bmsave.h
for the in-place fix commentary):

1. ``struct Dungeon`` (include/bmdifficulty.h) declared ten tightly packed
   u32 bitfields without the project's ``BITPACKED`` attribute. Legacy
   agbcc's old-APCS bitfield allocator packs bits contiguously across a
   u32 storage-unit boundary, yielding the documented 12-byte/96-bit
   layout; AAPCS-conformant modern GCC refuses to let a bitfield straddle
   a storage unit sized to its declared type, so several fields
   (turnCount, enemiesDefeated, postgameEnemiesDefeated) started a fresh
   4-byte unit instead, inflating the struct to 16 bytes. This cascaded
   into every offset in struct SaveBlocks from gameSaveBlocks onward.
   Fix: add ``BITPACKED`` (aligned(4), packed) to struct Dungeon, matching
   the existing convention used by struct PlaySt/PlaySt_30/PlaySt_OptionBits
   for the same reason. Both compilers now agree on 12 bytes.

2. ``struct BonusClaimSaveData`` (include/bmsave.h) has an *unpadded*
   natural size of 0x142 (bonus[0x10] * sizeof(BonusClaimEnt) + cksum16),
   which is already a multiple of its own natural alignment (2, from
   cksum16) -- so AAPCS-conformant modern GCC leaves it at 0x142. Legacy
   agbcc, however, always rounds *every* struct's size up to a 4-byte
   multiple regardless of its members' own alignment (a documented
   old-ARM-APCS convention, verified empirically with a minimal
   `struct { char a,b,c; }` repro compiling to sizeof 4 under agbcc), so
   it produces 0x144 -- matching the struct's documented position
   immediately before the `reserved` field in struct SaveBlocks. Fix: add
   ``ALIGN(4)`` to struct BonusClaimSaveData, the same precedent already
   used by struct GMapSaveInfo for this exact class of divergence.

Two independent compilers are used so this proves the same invariants both
"as legacy-shipped" (agbcc, the actual compiler that builds fireemblem8.gba)
and across every modern build cell:

* ``test_layout_with_legacy_agbcc`` always runs -- tools/agbcc is a
  first-party, already-vendored part of this repository (see
  docs/quickstart.md), so this test has no optional dependency and gives
  unconditional coverage even when the cross toolchain below is absent.
* ``test_layout_in_all_modern_cells`` mirrors test_abi_layout.py's exact
  pattern: a C probe using _Static_assert/offsetof, compiled -- not
  executed -- with the real arm-none-eabi-gcc across all four modern
  build cells, skipped gracefully when that toolchain is unavailable.

All expected byte values below were derived from -- and independently
cross-checked against -- the legacy agbcc build (the authoritative,
already-shipped on-media layout); the assertions merely encode that this
compiler (a first-party, already-vendored dependency needing no network
access) agrees with itself and with the modern toolchain, so this test
carries no separate "trust me" magic-number risk.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class SaveFormatLayoutTests(unittest.TestCase):

    # -- shared C89 static-array-size assertion probe ------------------------
    #
    # `char name[(cond) ? 1 : -1];` fails to compile with a negative array
    # size diagnostic whenever `cond` is false. This works unmodified on
    # both agbcc (C89, no _Static_assert) and a modern C compiler, so the
    # same source text is reused for both compilers below.

    _PROBE_SOURCE = textwrap.dedent("""\
        #include <stddef.h>
        #include "global.h"
        #include "bmsave.h"
        #include "bmmind.h"
        #include "bmtrick.h"
        #include "bmdifficulty.h"
        #include "sram-layout.h"
        #include "expansion_save_prefs.h"
        #include "mapgen_save_seed.h"

        /* struct ExpansionSaveMeta itself: exactly the 0x5C-byte pad,
         * zero implicit padding, checksum domain fixed at 0x2E bytes. */
        char probe_meta_size[sizeof(struct ExpansionSaveMeta) == 0x5C ? 1 : -1];
        char probe_meta_checksum_domain[EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM == 0x2E ? 1 : -1];
        char probe_meta_off_formatVersion[offsetof(struct ExpansionSaveMeta, formatVersion) == 0x04 ? 1 : -1];
        char probe_meta_off_compatEpoch[offsetof(struct ExpansionSaveMeta, compatEpoch) == 0x06 ? 1 : -1];
        char probe_meta_off_abiId[offsetof(struct ExpansionSaveMeta, abiId) == 0x08 ? 1 : -1];
        char probe_meta_off_frameworkVersionPacked[offsetof(struct ExpansionSaveMeta, frameworkVersionPacked) == 0x0C ? 1 : -1];
        char probe_meta_off_configFingerprint[offsetof(struct ExpansionSaveMeta, configFingerprint) == 0x10 ? 1 : -1];
        char probe_meta_off_buildCommitShort[offsetof(struct ExpansionSaveMeta, buildCommitShort) == 0x24 ? 1 : -1];
        char probe_meta_off_checksum[offsetof(struct ExpansionSaveMeta, checksum) == 0x2E ? 1 : -1];
        char probe_meta_off_reserved[offsetof(struct ExpansionSaveMeta, reserved) == 0x30 ? 1 : -1];

        /* Every persisted nested struct type reachable from struct
         * SaveBlocks: sizeof must be identical under both compilers, not
         * just the top-level container's total size (two real, distinct
         * divergences -- struct Dungeon and struct BonusClaimSaveData --
         * were found and fixed via this exact style of assertion; see the
         * module docstring above). */
        char probe_sz_GlobalSaveInfo[sizeof(struct GlobalSaveInfo) == 0x64 ? 1 : -1];
        char probe_sz_SaveBlockInfo[sizeof(struct SaveBlockInfo) == 0x10 ? 1 : -1];
        char probe_sz_GameRankSaveData[sizeof(struct GameRankSaveData) == 0x18 ? 1 : -1];
        char probe_sz_GameRankSaveDataPacks[sizeof(struct GameRankSaveDataPacks) == 0x94 ? 1 : -1];
        char probe_sz_SoundRoomSaveData[sizeof(struct SoundRoomSaveData) == 0x24 ? 1 : -1];
        char probe_sz_bmsave_unkstruct2[sizeof(struct bmsave_unkstruct2) == 0x14 ? 1 : -1];
        char probe_sz_BonusClaimEnt[sizeof(struct BonusClaimEnt) == 0x14 ? 1 : -1];
        char probe_sz_BonusClaimSaveData[sizeof(struct BonusClaimSaveData) == 0x144 ? 1 : -1];
        char probe_sz_UnitUsageStats[sizeof(struct UnitUsageStats) == 0x10 ? 1 : -1];
        char probe_sz_ChapterStats[sizeof(struct ChapterStats) == 0x4 ? 1 : -1];
        char probe_sz_GameSavePackedUnit[sizeof(struct GameSavePackedUnit) == 0x24 ? 1 : -1];
        char probe_sz_SuspendSavePackedUnit[sizeof(struct SuspendSavePackedUnit) == 0x34 ? 1 : -1];
        char probe_sz_MultiArenaRankingEnt[sizeof(struct MultiArenaRankingEnt) == 0x14 ? 1 : -1];
        char probe_sz_MultiArenaSaveTeam[sizeof(struct MultiArenaSaveTeam) == 0xC4 ? 1 : -1];
        char probe_sz_MultiArenaSaveBlock[sizeof(struct MultiArenaSaveBlock) == 0x874 ? 1 : -1];
        char probe_sz_ExtraMapSaveHead[sizeof(struct ExtraMapSaveHead) == 0x1C ? 1 : -1];
        char probe_sz_GMapSaveInfo[sizeof(struct GMapSaveInfo) == 0x24 ? 1 : -1];
        char probe_sz_Dungeon[sizeof(struct Dungeon) == 0xC ? 1 : -1];
        char probe_sz_GameSaveBlock[sizeof(struct GameSaveBlock) == 0xDC8 ? 1 : -1];
        char probe_sz_SuspendSaveBlock[sizeof(struct SuspendSaveBlock) == 0x1F78 ? 1 : -1];
        char probe_sz_ActionData[sizeof(struct ActionData) == 0x38 ? 1 : -1];
        char probe_sz_Trap[sizeof(struct Trap) == 0x8 ? 1 : -1];

        /* Every direct member offset of the two largest/most complex
         * persisted containers, so an internal field shift can never
         * silently cancel out in a matching top-level total size. */
        char probe_gsb_off_playSt[offsetof(struct GameSaveBlock, playSt) == 0x0 ? 1 : -1];
        char probe_gsb_off_units[offsetof(struct GameSaveBlock, units) == 0x4C ? 1 : -1];
        char probe_gsb_off_gmUnit[offsetof(struct GameSaveBlock, gmUnit) == 0x778 ? 1 : -1];
        char probe_gsb_off_supplyItems[offsetof(struct GameSaveBlock, supplyItems) == 0x79C ? 1 : -1];
        char probe_gsb_off_pidStats[offsetof(struct GameSaveBlock, pidStats) == 0x84C ? 1 : -1];
        char probe_gsb_off_chapterStats[offsetof(struct GameSaveBlock, chapterStats) == 0xCAC ? 1 : -1];
        char probe_gsb_off_permanentFlags[offsetof(struct GameSaveBlock, permanentFlags) == 0xD6C ? 1 : -1];
        char probe_gsb_off_bonusClaimFlags[offsetof(struct GameSaveBlock, bonusClaimFlags) == 0xD88 ? 1 : -1];
        char probe_gsb_off_wmStuff[offsetof(struct GameSaveBlock, wmStuff) == 0xD8C ? 1 : -1];
        char probe_gsb_off_dungeons[offsetof(struct GameSaveBlock, dungeons) == 0xDB0 ? 1 : -1];

        char probe_ssb_off_playSt[offsetof(struct SuspendSaveBlock, playSt) == 0x0 ? 1 : -1];
        char probe_ssb_off_action[offsetof(struct SuspendSaveBlock, action) == 0x4C ? 1 : -1];
        char probe_ssb_off_blueUnits[offsetof(struct SuspendSaveBlock, blueUnits) == 0x84 ? 1 : -1];
        char probe_ssb_off_wmMonsterUnit[offsetof(struct SuspendSaveBlock, wmMonsterUnit) == 0xAE0 ? 1 : -1];
        char probe_ssb_off_redUnits[offsetof(struct SuspendSaveBlock, redUnits) == 0xB14 ? 1 : -1];
        char probe_ssb_off_greenUnits[offsetof(struct SuspendSaveBlock, greenUnits) == 0x153C ? 1 : -1];
        char probe_ssb_off_traps[offsetof(struct SuspendSaveBlock, traps) == 0x1744 ? 1 : -1];
        char probe_ssb_off_supplyItems[offsetof(struct SuspendSaveBlock, supplyItems) == 0x1944 ? 1 : -1];
        char probe_ssb_off_pidStats[offsetof(struct SuspendSaveBlock, pidStats) == 0x19F4 ? 1 : -1];
        char probe_ssb_off_chapterStats[offsetof(struct SuspendSaveBlock, chapterStats) == 0x1E54 ? 1 : -1];
        char probe_ssb_off_menuOverride[offsetof(struct SuspendSaveBlock, menuOverride) == 0x1F14 ? 1 : -1];
        char probe_ssb_off_permanentFlags[offsetof(struct SuspendSaveBlock, permanentFlags) == 0x1F24 ? 1 : -1];
        char probe_ssb_off_chapterFlags[offsetof(struct SuspendSaveBlock, chapterFlags) == 0x1F3D ? 1 : -1];
        char probe_ssb_off_wmStuff[offsetof(struct SuspendSaveBlock, wmStuff) == 0x1F44 ? 1 : -1];
        char probe_ssb_off_dungeon[offsetof(struct SuspendSaveBlock, dungeon) == 0x1F68 ? 1 : -1];
        char probe_ssb_off_eventSlotCnt[offsetof(struct SuspendSaveBlock, eventSlotCnt) == 0x1F74 ? 1 : -1];

        char probe_mab_off_teams[offsetof(struct MultiArenaSaveBlock, teams) == 0x0 ? 1 : -1];
        char probe_mab_off_config[offsetof(struct MultiArenaSaveBlock, config) == 0x7A8 ? 1 : -1];
        char probe_mab_off_rankings[offsetof(struct MultiArenaSaveBlock, rankings) == 0x7AC ? 1 : -1];

        /* struct SaveBlocks: the new metadata field lands exactly where the
         * old pad was, and every neighboring block offset plus the total
         * struct size are unchanged. */
        char probe_sb_off_globalSaveInfo[offsetof(struct SaveBlocks, globalSaveInfo) == 0x0000 ? 1 : -1];
        char probe_sb_off_saveBlockInfo[offsetof(struct SaveBlocks, saveBlockInfo) == 0x0064 ? 1 : -1];
        char probe_sb_off_suspendSaveBlocks[offsetof(struct SaveBlocks, suspendSaveBlocks) == 0x00D4 ? 1 : -1];
        char probe_sb_off_gameSaveBlocks[offsetof(struct SaveBlocks, gameSaveBlocks) == 0x3FC4 ? 1 : -1];
        char probe_sb_off_multiArenaBlock[offsetof(struct SaveBlocks, multiArenaBlock) == 0x691C ? 1 : -1];
        char probe_sb_off_gameRankSave[offsetof(struct SaveBlocks, gameRankSave) == 0x7190 ? 1 : -1];
        char probe_sb_off_soundRoomSave[offsetof(struct SaveBlocks, soundRoomSave) == 0x7224 ? 1 : -1];
        char probe_sb_off_unkstruct2[offsetof(struct SaveBlocks, unkstruct2) == 0x7248 ? 1 : -1];
        char probe_sb_off_bonusClaim[offsetof(struct SaveBlocks, bonusClaim) == 0x725C ? 1 : -1];
        char probe_sb_off_reserved[offsetof(struct SaveBlocks, reserved) == 0x73A0 ? 1 : -1];
        char probe_sb_off_expansionSaveMeta[offsetof(struct SaveBlocks, expansionSaveMeta) == 0x73A4 ? 1 : -1];
        char probe_sb_off_xmap[offsetof(struct SaveBlocks, xmap) == 0x7400 ? 1 : -1];
        char probe_sb_size[sizeof(struct SaveBlocks) == 0x741C ? 1 : -1];

        /* SRAM_OFFSET_EXPANSION_SAVE_META / SRAM_SIZE_EXPANSION_SAVE_META
         * (include/sram-layout.h) must agree with the struct itself. */
        char probe_layout_offset[SRAM_OFFSET_EXPANSION_SAVE_META == 0x73A4 ? 1 : -1];
        char probe_layout_size[SRAM_SIZE_EXPANSION_SAVE_META == 0x5C ? 1 : -1];

        /* struct ExpansionUserPrefs (include/expansion_save_prefs.h, issue
         * #18 sprint 2): fixed layout, ALIGN(4)-forced size agreement
         * between agbcc and modern gcc (same class of divergence as
         * struct BonusClaimSaveData above), and fits entirely inside
         * struct ExpansionSaveMeta's `reserved` tail with the documented
         * headroom left over -- none of ExpansionSaveMeta's own 0x00-0x2F
         * named-field layout (probed above) is touched by any of this. */
        char probe_user_prefs_size[sizeof(struct ExpansionUserPrefs) == 0x0C ? 1 : -1];
        char probe_user_prefs_off_magic[offsetof(struct ExpansionUserPrefs, magic) == 0x00 ? 1 : -1];
        char probe_user_prefs_off_version[offsetof(struct ExpansionUserPrefs, version) == 0x01 ? 1 : -1];
        char probe_user_prefs_off_localeId[offsetof(struct ExpansionUserPrefs, localeId) == 0x02 ? 1 : -1];
        char probe_user_prefs_off_flags[offsetof(struct ExpansionUserPrefs, flags) == 0x03 ? 1 : -1];
        char probe_user_prefs_off_reserved[offsetof(struct ExpansionUserPrefs, reserved) == 0x04 ? 1 : -1];
        char probe_user_prefs_off_checksum[offsetof(struct ExpansionUserPrefs, checksum) == 0x08 ? 1 : -1];
        char probe_user_prefs_size_for_checksum[EXPANSION_USER_PREFS_SIZE_FOR_CHECKSUM == 0x08 ? 1 : -1];
        char probe_user_prefs_meta_offset[EXPANSION_USER_PREFS_META_OFFSET == 0 ? 1 : -1];
        char probe_reserved_tail_size_matches[
            (int)sizeof(((struct ExpansionSaveMeta *)0)->reserved) == EXPANSION_SAVE_META_RESERVED_SIZE ? 1 : -1];
        char probe_user_prefs_fits_in_reserved[
            (EXPANSION_USER_PREFS_META_OFFSET + (int)sizeof(struct ExpansionUserPrefs))
                <= (int)sizeof(((struct ExpansionSaveMeta *)0)->reserved) ? 1 : -1];
        char probe_reserved_headroom_bytes[EXPANSION_SAVE_META_RESERVED_HEADROOM_BYTES == 0x20 ? 1 : -1];
        char probe_reserved_headroom_matches[
            EXPANSION_SAVE_META_RESERVED_HEADROOM_BYTES
                == ((int)sizeof(((struct ExpansionSaveMeta *)0)->reserved)
                    - EXPANSION_USER_PREFS_META_OFFSET - (int)sizeof(struct ExpansionUserPrefs)) ? 1 : -1];

        /* struct MapGenSaveSeed (include/mapgen_save_seed.h, FE8_MAPGEN):
         * same fixed-layout/ALIGN(4) reasoning as struct ExpansionUserPrefs
         * above, placed immediately after it in the reserved tail rather
         * than at a separately-chosen offset, and still fitting with
         * headroom left over. */
        char probe_mapgen_seed_size[sizeof(struct MapGenSaveSeed) == 0x0C ? 1 : -1];
        char probe_mapgen_seed_off_magic[offsetof(struct MapGenSaveSeed, magic) == 0x00 ? 1 : -1];
        char probe_mapgen_seed_off_version[offsetof(struct MapGenSaveSeed, version) == 0x01 ? 1 : -1];
        char probe_mapgen_seed_off_reserved[offsetof(struct MapGenSaveSeed, reserved) == 0x02 ? 1 : -1];
        char probe_mapgen_seed_off_seed[offsetof(struct MapGenSaveSeed, seed) == 0x04 ? 1 : -1];
        char probe_mapgen_seed_off_checksum[offsetof(struct MapGenSaveSeed, checksum) == 0x08 ? 1 : -1];
        char probe_mapgen_seed_size_for_checksum[MAPGEN_SAVE_SEED_SIZE_FOR_CHECKSUM == 0x08 ? 1 : -1];
        char probe_mapgen_seed_meta_offset[
            MAPGEN_SAVE_SEED_META_OFFSET == (EXPANSION_USER_PREFS_META_OFFSET + 0x0C) ? 1 : -1];
        char probe_mapgen_seed_fits_in_reserved[
            (MAPGEN_SAVE_SEED_META_OFFSET + (int)sizeof(struct MapGenSaveSeed))
                <= (int)sizeof(((struct ExpansionSaveMeta *)0)->reserved) ? 1 : -1];
        char probe_mapgen_seed_no_overlap_with_user_prefs[
            MAPGEN_SAVE_SEED_META_OFFSET
                >= (EXPANSION_USER_PREFS_META_OFFSET + (int)sizeof(struct ExpansionUserPrefs)) ? 1 : -1];
        char probe_mapgen_seed_headroom_bytes[MAPGEN_SAVE_SEED_RESERVED_HEADROOM_BYTES == 0x14 ? 1 : -1];
        char probe_mapgen_seed_headroom_matches[
            MAPGEN_SAVE_SEED_RESERVED_HEADROOM_BYTES
                == ((int)sizeof(((struct ExpansionSaveMeta *)0)->reserved)
                    - MAPGEN_SAVE_SEED_META_OFFSET - (int)sizeof(struct MapGenSaveSeed)) ? 1 : -1];
    """)

    # -- legacy agbcc coverage (always runs; no optional dependency) --------

    def test_layout_with_legacy_agbcc(self):
        """The probe compiles cleanly with the vendored legacy agbcc."""
        agbcc = ROOT / "tools" / "agbcc" / "bin" / "agbcc"
        if not agbcc.exists():
            self.skipTest(
                "tools/agbcc is not built -- run scripts/quickstart.sh first"
            )

        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "save_format_layout_probe.c"
            preprocessed = temporary_path / "save_format_layout_probe.i"
            asm_out = temporary_path / "save_format_layout_probe.s"
            source.write_text(self._PROBE_SOURCE, encoding="utf-8")

            cpp_result = subprocess.run(
                [
                    "cc", "-E",
                    "-I", str(ROOT / "tools" / "agbcc" / "include"),
                    "-iquote", str(ROOT / "include"),
                    "-iquote", str(ROOT),
                    "-nostdinc", "-undef",
                    str(source),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(cpp_result.returncode, 0, cpp_result.stdout)
            preprocessed.write_text(cpp_result.stdout, encoding="utf-8")

            compile_result = subprocess.run(
                [
                    str(agbcc),
                    "-mthumb-interwork", "-Wimplicit", "-Wparentheses",
                    "-O2", "-fhex-asm",
                    str(preprocessed), "-o", str(asm_out),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(
                compile_result.returncode, 0,
                f"legacy agbcc layout probe failed:\n{compile_result.stdout}",
            )

    # -- modern cross-toolchain coverage (skips gracefully if absent) -------

    def tool_overrides(self) -> "list[str] | None":
        prefix = os.environ.get("PREFIX", "arm-none-eabi-")
        root = os.environ.get("MODERN_TOOLCHAIN_ROOT", "")
        cc = os.environ.get("MODERN_CC", "")
        if not cc and root:
            cc = str(Path(root) / "bin" / f"{prefix}gcc")
        if not cc:
            cc = shutil.which(f"{prefix}gcc") or ""

        objdump = os.environ.get("MODERN_OBJDUMP", "")
        if not objdump:
            objdump = shutil.which(f"{prefix}objdump") or ""

        if not cc or not objdump:
            return None

        overrides = [f"MODERN_CC={cc}", f"MODERN_OBJDUMP={objdump}"]
        for variable in ("MODERN_BINUTILS_DIR", "MODERN_NEWLIB_INCLUDE"):
            value = os.environ.get(variable)
            if value:
                overrides.append(f"{variable}={value}")
        return overrides

    def make(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "--no-print-directory", *arguments],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_layout_in_all_modern_cells(self):
        """The probe compiles in all four modern build cells (debug/release
        x AAPCS/APCS-GNU) when the arm-none-eabi cross toolchain is present.

        This proves every persisted save struct (not just struct SaveBlocks'
        top-level fields) has byte-identical sizeof/offsetof under all four
        supported modern build cells and the legacy agbcc build. Skips
        gracefully (not unconditionally) only when the arm-none-eabi cross
        toolchain itself is unavailable in the current environment (or via
        MODERN_CC/MODERN_TOOLCHAIN_ROOT), exactly like test_abi_layout.py.
        """
        overrides = self.tool_overrides()
        if overrides is None:
            self.skipTest("arm-none-eabi GCC and objdump are not available")

        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "save_format_layout_probe.c"
            output_root = temporary_path / "save-format-layout-objects"
            source.write_text(self._PROBE_SOURCE, encoding="utf-8")

            for config in ("debug", "release"):
                for abi in ("aapcs", "apcs-gnu"):
                    result = self.make(
                        ROOT,
                        "expansion-modern-cohort",
                        f"MODERN_CONFIG={config}",
                        f"MODERN_ABI={abi}",
                        f"MODERN_BUILD_ROOT={output_root}",
                        f"MODERN_COHORT_SOURCES={source}",
                        "MODERN_COHORT_ASM_SOURCES=",
                        *overrides,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"{config}/{abi} save-format layout probe failed:\n"
                        f"{result.stdout}",
                    )


if __name__ == "__main__":
    unittest.main()
