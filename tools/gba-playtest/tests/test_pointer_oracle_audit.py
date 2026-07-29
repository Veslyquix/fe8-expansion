"""Focused pointer-oracle audit for every checked-in playtest scenario and
fingerprint.

Independent code review (issue #11/#13 remediation) flagged that a behavior
scenario must never assert a raw, relocated pointer value as its runtime
oracle: a 4-byte ``expected``/``value`` that happens to be a live ROM
(``0x08xxxxxx``), EWRAM (``0x0202xxxx``), IWRAM (``0x0300xxxx``) or cart-SRAM
address is layout/relocation-dependent -- it re-encodes *where code or data
landed after linking*, not *what the game semantically did*. A relinked or
relocated build shifts those addresses, so such an assertion can pass or fail
for reasons that have nothing to do with the behavior under test (and can even
mask a genuinely broken build whose pointers coincidentally realign).

Every runtime proof must instead be a relocation-independent semantic value:
a unit's HP, a proc/hub counter, a status flag, a null-vs-non-null field
transition, a menu label read as inline text, etc. Those survive relocation.

This is a black-box, code-level guarantee: it needs no libmGBA or ARM
toolchain, so it always runs (never skipped) in the fast host-only lane and
is the standing regression gate that keeps pointer oracles from creeping back
into any scenario or fingerprint.

Default posture is REJECT: any 4-byte probe value inside a pointer range is a
failure unless it appears in ``_REVIEWED_ALLOWLIST`` below with an explicit
human-reviewed justification. The allowlist is intentionally empty -- there is
currently no legitimate pointer-valued behavior oracle in the corpus.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
SCENARIOS_DIR = PLAYTEST_DIR / "scenarios"
FINGERPRINTS_DIR = PLAYTEST_DIR / "fingerprints"

sys.path.insert(0, str(PLAYTEST_DIR))
import gba_playtest  # noqa: E402

# GBA address regions a 4-byte probe value could be a live pointer into. A
# semantic scalar (small counter, status byte, packed magic like "DBL1"
# 0x44424c31, a null 0x00000000) never lands in any of these; only a real
# ROM/RAM/SRAM address does.
_POINTER_RANGES = (
    (0x02000000, 0x0203FFFF),  # EWRAM
    (0x03000000, 0x03007FFF),  # IWRAM
    (0x08000000, 0x0DFFFFFF),  # cart ROM + its wait-state mirrors
    (0x0E000000, 0x0E00FFFF),  # cart SRAM
)

# (file_name, checkpoint_name, address, value, reason). Intentionally empty:
# a pointer-valued oracle is rejected by default and may only be admitted
# here after explicit human review with a written, durable justification --
# never as a silent, documentation-only exemption.
_REVIEWED_ALLOWLIST: frozenset[tuple[str, str, str, str]] = frozenset()


def _in_pointer_range(value: int) -> bool:
    return any(start <= value <= end for start, end in _POINTER_RANGES)


def _iter_scenario_probe_values():
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        scenario = gba_playtest.load_scenario(path)
        for checkpoint in scenario.checkpoints:
            for probe in checkpoint.probes:
                if probe.expected is None:
                    continue
                yield path.name, checkpoint.name, probe.address, probe.size, probe.expected


def _iter_fingerprint_probe_values():
    for path in sorted(FINGERPRINTS_DIR.glob("*.json")):
        data = gba_playtest.validate_fingerprint(
            json.loads(path.read_text(encoding="utf-8")), str(path)
        )
        for checkpoint in data["checkpoints"]:
            for probe in checkpoint["probes"]:
                value = probe.get("value")
                if value is None:
                    continue
                address = int(probe["address"], 16)
                yield path.name, checkpoint["name"], address, int(probe["size"]), value


def _offenders(rows):
    offenders = []
    for file_name, checkpoint_name, address, size, value in rows:
        if size < 4:
            # A value narrower than 4 bytes cannot hold a 32-bit pointer.
            continue
        parsed = int(value, 16) if isinstance(value, str) else int(value)
        if not _in_pointer_range(parsed):
            continue
        key = (file_name, checkpoint_name, f"0x{address:08x}", f"0x{parsed:08x}")
        if key in _REVIEWED_ALLOWLIST:
            continue
        offenders.append(
            f"{file_name} :: {checkpoint_name} :: probe 0x{address:08x}/{size} "
            f"asserts pointer-range value 0x{parsed:08x}"
        )
    return offenders


class PointerOracleAuditTests(unittest.TestCase):
    def test_scenarios_have_no_pointer_oracles(self):
        offenders = _offenders(_iter_scenario_probe_values())
        self.assertEqual(
            offenders,
            [],
            "checked-in scenarios must not assert relocated pointer values as behavior "
            "oracles (use relocation-independent semantic probes instead):\n  - "
            + "\n  - ".join(offenders),
        )

    def test_fingerprints_have_no_pointer_oracles(self):
        offenders = _offenders(_iter_fingerprint_probe_values())
        self.assertEqual(
            offenders,
            [],
            "checked-in fingerprints must not carry relocated pointer values as behavior "
            "oracles (re-capture from a scenario whose probes are semantic):\n  - "
            + "\n  - ".join(offenders),
        )

    def test_audit_actually_scanned_the_corpus(self):
        # Guards against a silently-empty scan (e.g. a moved directory) laundering
        # into a false pass: the corpus is large and must be non-trivial.
        scenario_values = list(_iter_scenario_probe_values())
        fingerprint_values = list(_iter_fingerprint_probe_values())
        self.assertGreater(len(scenario_values), 100, "expected a substantial scenario probe corpus")
        self.assertGreater(len(fingerprint_values), 100, "expected a substantial fingerprint probe corpus")

    def test_allowlist_entries_are_all_still_present(self):
        # An allowlist entry that no longer matches any probe is stale and must be
        # removed, so the allowlist can never silently over-permit.
        live_keys = set()
        for file_name, checkpoint_name, address, size, value in list(
            _iter_scenario_probe_values()
        ) + list(_iter_fingerprint_probe_values()):
            parsed = int(value, 16) if isinstance(value, str) else int(value)
            live_keys.add((file_name, checkpoint_name, f"0x{address:08x}", f"0x{parsed:08x}"))
        stale = sorted(entry for entry in _REVIEWED_ALLOWLIST if entry not in live_keys)
        self.assertEqual(stale, [], f"stale allowlist entries must be removed: {stale}")


if __name__ == "__main__":
    unittest.main()
