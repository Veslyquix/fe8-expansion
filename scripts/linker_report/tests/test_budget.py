"""Unit tests for linker_report.budget."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import budget

FIXTURES = Path(__file__).parent / "fixtures"
BUDGET_PY = Path(__file__).parent.parent / "budget.py"
SCRATCH_DIR = Path(__file__).parent / ".scratch"
SCRATCH_DIR.mkdir(exist_ok=True)
ROOT = Path(__file__).resolve().parents[3]
REAL_MODERN_MAP = (
    ROOT / "build" / "expansion-modern" / "debug" / "aapcs" / "fireemblem8.map"
)


def run_budget(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUDGET_PY), *args],
        capture_output=True, text=True,
    )


class TestMapParsing(unittest.TestCase):
    """Core map-file parsing tests."""

    def make_output_path(self, suffix: str) -> Path:
        path = SCRATCH_DIR / f"{self._testMethodName}-{suffix}.json"
        path.unlink(missing_ok=True)
        self.addCleanup(lambda path=path: path.unlink(missing_ok=True))
        return path

    def test_basic_regions_and_sections(self):
        """Parse a minimal map and check region/section counts."""
        out = self.make_output_path("basic")
        r = run_budget("--map", str(FIXTURES / "basic.map"), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(out.read_text())
        self.assertEqual(report["schema_version"], 1)
        # 3 non-default regions
        self.assertEqual(len(report["regions"]), 3)
        names = {reg["name"] for reg in report["regions"]}
        self.assertEqual(names, {"rom", "iwram", "ewram"})
        # 3 output sections (ewram_data, IWRAM, ROM)
        self.assertEqual(len(report["sections"]), 3)
        # No overlays in basic
        self.assertEqual(len(report["overlays"]), 0)
        self.assertFalse(report["overflow"])

    def test_overlay_detection(self):
        """Overlays sharing an address are detected with correct peak."""
        out = self.make_output_path("overlay")
        r = run_budget("--map", str(FIXTURES / "overlay.map"), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(out.read_text())
        overlays = report["overlays"]
        self.assertEqual(len(overlays), 3)
        # All at same address
        for ov in overlays:
            self.assertEqual(ov["address"], 0x02000000)
            self.assertEqual(ov["region"], "ewram")
        # Peak is the largest: ewram_overlay_banim = 0x20188
        for ov in overlays:
            self.assertEqual(ov["peak_bytes"], 0x20188)
        # Individual sizes
        by_name = {ov["name"]: ov for ov in overlays}
        self.assertEqual(by_name["ewram_overlay_0"]["size_bytes"], 0x1f19c)
        self.assertEqual(by_name["ewram_overlay_banim"]["size_bytes"], 0x20188)
        self.assertEqual(by_name["ewram_overlay_sio"]["size_bytes"], 0x1188)

    def test_region_overflow_exits_nonzero(self):
        """EWRAM exceeding capacity triggers exit code 1."""
        out = self.make_output_path("overflow")
        r = run_budget("--map", str(FIXTURES / "overflow.map"), "--output", str(out))
        self.assertEqual(r.returncode, 1)
        report = json.loads(out.read_text())
        self.assertTrue(report["overflow"])
        ewram = next(reg for reg in report["regions"] if reg["name"] == "ewram")
        self.assertTrue(ewram["overflow"])
        self.assertEqual(ewram["occupied_bytes"], 0x50000)

    def test_malformed_map_exits_2(self):
        """A map file with no Memory Configuration returns exit 2."""
        out = self.make_output_path("malformed")
        r = run_budget("--map", str(FIXTURES / "malformed.map"), "--output", str(out))
        self.assertEqual(r.returncode, 2)

    def test_deterministic_output(self):
        """Two runs on the same input produce byte-identical JSON."""
        out1 = self.make_output_path("deterministic-1")
        out2 = self.make_output_path("deterministic-2")
        run_budget("--map", str(FIXTURES / "overlay.map"), "--output", str(out1))
        run_budget("--map", str(FIXTURES / "overlay.map"), "--output", str(out2))
        self.assertEqual(out1.read_text(), out2.read_text())

    def test_unmapped_debug_sections_are_excluded(self):
        map_path = SCRATCH_DIR / f"{self._testMethodName}.map"
        map_path.write_text(
            (FIXTURES / "basic.map").read_text()
            + "\n.debug_info     0x00000000 0x1234\n"
        )
        self.addCleanup(lambda: map_path.unlink(missing_ok=True))
        out = self.make_output_path("no-debug")
        r = run_budget("--map", str(map_path), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        names = {section["name"] for section in json.loads(out.read_text())["sections"]}
        self.assertNotIn(".debug_info", names)

    def test_check_mode_passes_on_match(self):
        """--check succeeds when report matches."""
        out = self.make_output_path("check-pass")
        run_budget("--map", str(FIXTURES / "basic.map"), "--output", str(out))
        r = run_budget("--map", str(FIXTURES / "basic.map"), "--output", str(out), "--check")
        self.assertEqual(r.returncode, 0)

    def test_check_mode_fails_on_drift(self):
        """--check exits 1 when report content differs."""
        out = self.make_output_path("check-fail")
        # Write with basic, check against overlay (different content)
        run_budget("--map", str(FIXTURES / "basic.map"), "--output", str(out))
        r = run_budget("--map", str(FIXTURES / "overlay.map"), "--output", str(out), "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("--- committed", r.stderr)
        self.assertIn("+++ generated", r.stderr)

    def test_check_mode_ignores_optional_elf_diagnostics(self):
        out = self.make_output_path("check-elf")
        run_budget("--map", str(FIXTURES / "basic.map"), "--output", str(out))
        report = json.loads(out.read_text())
        report["elf"] = {
            "available": True,
            "section_count": 999,
            "sections": [{"name": "host-specific", "size_bytes": 123}],
            "cross_validation": {
                "in_elf_not_map": ["host-specific"],
                "in_map_not_elf": [],
            },
        }
        out.write_text(json.dumps(report, indent=2) + "\n")

        r = run_budget(
            "--map", str(FIXTURES / "basic.map"), "--output", str(out), "--check"
        )
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_check_mode_ignores_derived_end_markers(self):
        out = self.make_output_path("check-derived")
        run_budget("--map", str(FIXTURES / "basic.map"), "--output", str(out))
        report = json.loads(out.read_text())
        report["pinned_assignments"].append({
            "name": "__floating_end",
            "address": 0x08B00000,
            "expression": ".",
            "region": "rom",
        })
        out.write_text(json.dumps(report, indent=2) + "\n")

        r = run_budget(
            "--map", str(FIXTURES / "basic.map"), "--output", str(out), "--check"
        )
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_current_elf_section_mismatch_is_rejected(self):
        report = {
            "elf": {
                "available": True,
                "cross_validation": {
                    "in_elf_not_map": ["unexpected"],
                    "in_map_not_elf": [],
                },
            },
        }
        self.assertEqual(
            budget.elf_cross_validation_errors(report),
            ["in_elf_not_map: unexpected"],
        )

    def test_required_elf_validation_fails_closed_when_unavailable(self):
        report = {"elf": {"available": False}}

        self.assertEqual(budget.elf_cross_validation_errors(report), [])
        self.assertEqual(
            budget.elf_cross_validation_errors(
                report, require_available=True,
            ),
            ["ELF cross-validation unavailable"],
        )

    def test_empty_locale_output_is_not_an_alloc_section_mismatch(self):
        report = budget.generate_report(
            [budget.MemoryRegion("rom", 0x08000000, 0x01000000)],
            [
                budget.OutputSection("ROM", 0x08000000, 0x100),
                budget.OutputSection(".locale_data", 0x09000000, 0),
            ],
            [],
            [
                budget.ElfSection(
                    "ROM", "PROGBITS", 0x08000000, 0x100, "AX"
                ),
                budget.ElfSection(
                    ".locale_data", "PROGBITS", 0x09000000, 0, "A"
                ),
            ],
        )

        self.assertEqual(
            report["elf"]["cross_validation"],
            {"in_elf_not_map": [], "in_map_not_elf": []},
        )
        self.assertIn(
            ".locale_data",
            {section["name"] for section in report["sections"]},
        )

    def test_populated_locale_output_must_exist_in_allocatable_elf(self):
        report = budget.generate_report(
            [budget.MemoryRegion("rom", 0x08000000, 0x02000000)],
            [
                budget.OutputSection("ROM", 0x08000000, 0x100),
                budget.OutputSection(".locale_data", 0x09000000, 0x200),
            ],
            [],
            [
                budget.ElfSection(
                    "ROM", "PROGBITS", 0x08000000, 0x100, "AX"
                ),
            ],
        )

        self.assertEqual(
            budget.elf_cross_validation_errors(report),
            ["in_map_not_elf: .locale_data"],
        )

    def test_populated_locale_output_matches_allocatable_elf(self):
        report = budget.generate_report(
            [budget.MemoryRegion("rom", 0x08000000, 0x02000000)],
            [
                budget.OutputSection("ROM", 0x08000000, 0x100),
                budget.OutputSection(".locale_data", 0x09000000, 0x200),
            ],
            [],
            [
                budget.ElfSection(
                    "ROM", "PROGBITS", 0x08000000, 0x100, "AX"
                ),
                budget.ElfSection(
                    ".locale_data", "PROGBITS", 0x09000000, 0x200, "A"
                ),
            ],
        )

        self.assertEqual(budget.elf_cross_validation_errors(report), [])

    def test_positive_headroom_requirement_rejects_full_region(self):
        report = {
            "regions": [
                {
                    "name": "ewram",
                    "free_bytes": 0,
                    "overflow": False,
                },
                {
                    "name": "iwram",
                    "free_bytes": 1,
                    "overflow": False,
                },
            ]
        }

        self.assertEqual(
            budget.positive_headroom_errors(report, ["ewram", "iwram"]),
            [
                "ewram requires positive headroom: "
                "free_bytes=0 overflow=False"
            ],
        )

    def test_pinned_assignments_captured(self):
        """Symbol assignments at GBA addresses are recorded."""
        out = self.make_output_path("pinned")
        r = run_budget("--map", str(FIXTURES / "basic.map"), "--output", str(out))
        self.assertEqual(r.returncode, 0)
        report = json.loads(out.read_text())
        pinned = report["pinned_assignments"]
        names = {p["name"] for p in pinned}
        self.assertIn("__text_start", names)
        self.assertIn("__ewram_start", names)
        self.assertIn("__iwram_start", names)
        self.assertIn("__sp_irq", names)
        self.assertIn("__iwram_top", names)

    def test_boundary_pinned_assignments_are_marked(self):
        """Region-end marker assignments are tagged as boundaries."""
        out = self.make_output_path("boundary")
        r = run_budget("--map", str(FIXTURES / "basic.map"), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(out.read_text())
        by_name = {entry["name"]: entry for entry in report["pinned_assignments"]}
        self.assertEqual(by_name["__sp_irq"]["region"], "iwram")
        self.assertNotIn("boundary", by_name["__sp_irq"])
        self.assertEqual(by_name["__iwram_top"]["region"], "iwram")
        self.assertTrue(by_name["__iwram_top"]["boundary"])

    def test_overlay_growth_detects_overflow(self):
        """Overlay peak beyond both coverage and capacity triggers overflow."""
        out = self.make_output_path("overlay-growth")
        r = run_budget("--map", str(FIXTURES / "overlay_growth.map"), "--output", str(out))
        self.assertEqual(r.returncode, 1)
        report = json.loads(out.read_text())
        ewram = next(reg for reg in report["regions"] if reg["name"] == "ewram")
        self.assertTrue(report["overflow"])
        self.assertTrue(ewram["overflow"])
        self.assertEqual(ewram["occupied_bytes"], 0x42000)

    def test_overlay_contained_does_not_double_count(self):
        """Contained overlay peaks do not increase occupied bytes."""
        out = self.make_output_path("overlay-contained")
        r = run_budget("--map", str(FIXTURES / "overlay_contained.map"), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(out.read_text())
        ewram = next(reg for reg in report["regions"] if reg["name"] == "ewram")
        self.assertFalse(report["overflow"])
        self.assertFalse(ewram["overflow"])
        self.assertEqual(ewram["occupied_bytes"], 0x3efb8)

    def test_modern_map_all_overlays_parsed(self):
        """Modern map with load-address suffixes and empty overlays parses all 8."""
        out = self.make_output_path("modern-overlays")
        r = run_budget("--map", str(FIXTURES / "modern_overlays.map"), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(out.read_text())
        overlays = report["overlays"]
        self.assertEqual(len(overlays), 8)
        self.assertTrue(all(ov["address"] == 0x02000000 for ov in overlays))
        self.assertTrue(all(ov["peak_bytes"] == 0x2018C for ov in overlays))
        by_name = {ov["name"]: ov for ov in overlays}
        self.assertEqual(by_name["ewram_overlay_sio"]["size_bytes"], 0)
        self.assertEqual(by_name["ewram_overlay_worldmap"]["size_bytes"], 0)
        ewram = next(reg for reg in report["regions"] if reg["name"] == "ewram")
        self.assertEqual(ewram["occupied_bytes"], 0x2018C)

    def test_oneline_with_load_address(self):
        """One-line format with 'load address' suffix is parsed."""
        out = self.make_output_path("modern-oneline")
        r = run_budget("--map", str(FIXTURES / "modern_overlays.map"), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(out.read_text())
        by_name = {section["name"]: section for section in report["sections"]}
        self.assertEqual(by_name["ewram_data"]["address"], 0x02000000)
        self.assertEqual(by_name["ewram_data"]["size_bytes"], 0x1EC70)
        self.assertEqual(by_name["ewram_data"]["region"], "ewram")

    def test_dotprefixed_output_sections_are_parsed(self):
        """Dot-prefixed output sections are recognized in both map formats."""
        out = self.make_output_path("dotprefix")
        r = run_budget("--map", str(FIXTURES / "dotprefix.map"), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(out.read_text())
        self.assertEqual(
            {section["name"] for section in report["sections"]},
            {".text", ".data", ".bss"},
        )

    @unittest.skipUnless(REAL_MODERN_MAP.exists(), "modern map artifact not available")
    def test_real_modern_map_finds_all_overlays(self):
        """Integration: real modern map has 8 overlay sections."""
        out = self.make_output_path("real-modern")
        r = run_budget("--map", str(REAL_MODERN_MAP), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(out.read_text())
        overlays = report["overlays"]
        self.assertEqual(len(overlays), 8)
        self.assertTrue(all(ov["address"] == 0x02000000 for ov in overlays))
        peaks = {ov["peak_bytes"] for ov in overlays}
        self.assertEqual(peaks, {0x2018C})


if __name__ == "__main__":
    unittest.main()
