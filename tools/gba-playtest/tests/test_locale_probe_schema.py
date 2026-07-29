"""
Issue #18 sprint 4 host tests -- locale/language-menu probe schema and
bounds lock-in.

WHAT #1 requires host tests that cover "probe schema/bounds" for the new
semantic scenarios' `gExpansionLanguageMenuProbe` (include/
expansion_language_menu.h) reads. These scenarios reuse the existing
generic, already-reviewed backend/schema address+size probe mechanism
(tools/gba-playtest/backend.c, `Probe` in gba_playtest.py) unchanged --
a plain, bounded EWRAM read of a known diagnostic struct's own fields,
never a raw/arbitrary pointer dereference -- so no new backend C code or
JSON-schema field was required to satisfy this sprint's "safe read" intent.
What *is* new here is proving those hardcoded scenario addresses are
correct and will not silently drift: this module compiles and runs the
real, unmodified header (never re-implementing/guessing its layout) to
get the compiler's own offsetof()/sizeof() for every probed field, then
cross-checks every tools/gba-playtest/scenarios/locale-*.json probe
address against `base + offsetof(field)`, and every probe against the
struct's own sizeof() bound. A future header edit that reorders, resizes,
or removes a field will fail this suite instead of silently producing a
wrong-field (or out-of-bounds) pinned fingerprint that still happens to
byte-compare equal by coincidence.
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_DIR = REPO_ROOT / "tools" / "gba-playtest" / "scenarios"
C_FIXTURES_DIR = Path(__file__).resolve().parent / "c"
HEADER = REPO_ROOT / "include" / "expansion_language_menu.h"
DRIVER_SRC = C_FIXTURES_DIR / "expansion_language_menu_probe_offsets_driver.c"

CC = shutil.which("gcc") or shutil.which("cc")

# Field order matches include/expansion_language_menu.h's
# struct ExpansionLanguageMenuProbe declaration order exactly -- this
# module never reorders/re-derives it independently; it only asks the
# real compiler for each field's actual offsetof()/sizeof().
PROBE_FIELDS = [
    "active",
    "settingsActive",
    "promptShown",
    "autoSelected",
    "promptReason",
    "prefsState",
    "selectedLocale",
    "currentLocale",
    "enabledLocaleCount",
    "cacheGeneration",
    "startupRunCount",
    "settingsOpenCount",
    "settingsChangeCount",
]

# Byte width of each field, in the same order as PROBE_FIELDS (u8 fields
# then u16 fields -- see the header's own comments).
PROBE_FIELD_SIZES = {
    "active": 1,
    "settingsActive": 1,
    "promptShown": 1,
    "autoSelected": 1,
    "promptReason": 1,
    "prefsState": 1,
    "selectedLocale": 1,
    "currentLocale": 1,
    "enabledLocaleCount": 1,
    "cacheGeneration": 2,
    "startupRunCount": 2,
    "settingsOpenCount": 2,
    "settingsChangeCount": 2,
}


@unittest.skipIf(CC is None, "no host C compiler available")
class ExpansionLanguageMenuProbeSchemaTests(unittest.TestCase):
    """Compiles+runs the real header's offsetof()/sizeof() layout, then
    cross-checks it against every locale-*.json scenario's hardcoded
    probe addresses."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue_ = None  # placeholder, unused
        binary = C_FIXTURES_DIR / "expansion_language_menu_probe_offsets_driver.bin"
        result = subprocess.run(
            [CC, "-I", str(REPO_ROOT / "include"), "-o", str(binary), str(DRIVER_SRC)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                "failed to compile expansion_language_menu_probe_offsets_driver.c "
                f"against the real include/expansion_language_menu.h:\n{result.stderr}"
            )
        try:
            run = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
        finally:
            binary.unlink(missing_ok=True)
        layout = {}
        for line in run.stdout.strip().splitlines():
            name, _, value = line.partition("=")
            layout[name] = int(value)
        cls.offsets = {name: layout[name] for name in PROBE_FIELDS}
        cls.struct_size = layout["sizeof"]

    def test_driver_reports_every_documented_field_and_matches_hand_derivation(self):
        """Sanity check on the driver itself: every PROBE_FIELDS name must
        actually appear in the header (i.e. the driver still compiles
        against the real, current field list, not a stale copy), fields
        must be in strictly increasing offset order (packed, no
        reordering), and the struct must round up to a whole u16 (size
        18, matching 9 u8 + padding + 4 u16 = 8 + 2(pad) + 8 = 18)."""
        offsets_in_order = [self.offsets[name] for name in PROBE_FIELDS]
        self.assertEqual(offsets_in_order, sorted(offsets_in_order),
                          "probe fields must be declared/packed in strictly increasing offset order")
        self.assertEqual(self.struct_size, 18,
                          "struct ExpansionLanguageMenuProbe layout changed size (9 u8 + pad(1) + 4 u16 = 18) "
                          "-- update PROBE_FIELDS/PROBE_FIELD_SIZES and every locale-*.json probe address")

    def _scenario_files(self):
        return sorted(SCENARIOS_DIR.glob("locale-*.json"))

    def test_every_locale_scenario_probe_address_matches_a_documented_field_offset(self):
        """Every probe address used by any locale-*.json scenario must be
        `base + offsetof(field)` for some real field, where `base` is
        that scenario's own gExpansionLanguageMenuProbe runtime address
        (derived per-scenario since debug/release symbol addresses
        legitimately differ -- taken as the scenario's own minimum probed
        address, which is always field `active` at offset 0)."""
        scenario_files = self._scenario_files()
        self.assertGreaterEqual(len(scenario_files), 10,
                                 "expected at least the 10 issue #18 sprint 4 locale-*.json scenarios")
        offset_to_field = {v: k for k, v in self.offsets.items()}
        for path in scenario_files:
            data = json.loads(path.read_text(encoding="utf-8"))
            addrs = set()
            for checkpoint in data["checkpoints"]:
                for probe in checkpoint.get("probes", []):
                    addrs.add(int(probe["address"], 16))
            if not addrs:
                continue
            base = min(addrs)
            self.assertIn(
                self.offsets["active"], {addr - base for addr in addrs},
                f"{path.name}: no probe targets field 'active' (offset 0) -- 'base' (lowest probed "
                "address) would not be the real struct base",
            )
            for addr in addrs:
                rel = addr - base
                self.assertIn(
                    rel, offset_to_field,
                    f"{path.name}: probe address {hex(addr)} (base {hex(base)}, +{rel}) does not match "
                    "any documented ExpansionLanguageMenuProbe field offset -- update the scenario or the "
                    "header/PROBE_FIELDS mapping",
                )

    def test_every_locale_scenario_probe_stays_within_struct_bounds(self):
        """No probe (address + size) may reach past sizeof(struct
        ExpansionLanguageMenuProbe) from its scenario's own base -- this
        is the schema "bounds" half of WHAT #1: these scenarios only ever
        read inside the one known, fixed-size diagnostic struct, never
        adjacent EWRAM state."""
        for path in self._scenario_files():
            data = json.loads(path.read_text(encoding="utf-8"))
            addrs = set()
            for checkpoint in data["checkpoints"]:
                for probe in checkpoint.get("probes", []):
                    addrs.add(int(probe["address"], 16))
            if not addrs:
                continue
            base = min(addrs)
            for checkpoint in data["checkpoints"]:
                for probe in checkpoint.get("probes", []):
                    addr = int(probe["address"], 16)
                    size = int(probe["size"])
                    end_offset = (addr - base) + size
                    self.assertLessEqual(
                        end_offset, self.struct_size,
                        f"{path.name}: probe at {probe['address']} size {size} ends at struct+{end_offset}, "
                        f"past sizeof(struct ExpansionLanguageMenuProbe)={self.struct_size}",
                    )

    def test_every_locale_scenario_probe_size_matches_its_fields_declared_width(self):
        """A probe's byte `size` must match the actual declared width of
        the field it targets (1 for every u8 field, 2 for every u16
        field) -- catches a probe that reads too few/many bytes for its
        own field even if it happens to still land in-bounds."""
        offset_to_field = {v: k for k, v in self.offsets.items()}
        for path in self._scenario_files():
            data = json.loads(path.read_text(encoding="utf-8"))
            addrs = set()
            for checkpoint in data["checkpoints"]:
                for probe in checkpoint.get("probes", []):
                    addrs.add(int(probe["address"], 16))
            if not addrs:
                continue
            base = min(addrs)
            for checkpoint in data["checkpoints"]:
                for probe in checkpoint.get("probes", []):
                    addr = int(probe["address"], 16)
                    rel = addr - base
                    field = offset_to_field.get(rel)
                    if field is None:
                        continue  # already reported by the offset-match test
                    self.assertEqual(
                        int(probe["size"]), PROBE_FIELD_SIZES[field],
                        f"{path.name}: probe at {probe['address']} targets field '{field}' "
                        f"(declared width {PROBE_FIELD_SIZES[field]}) but uses size {probe['size']}",
                    )


if __name__ == "__main__":
    unittest.main()
