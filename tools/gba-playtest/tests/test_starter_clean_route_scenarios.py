"""
Issue #6 Sprint 1 clean-route runtime scenarios (schema/contract tests).

These cover the six scenarios that reach a REAL Prologue battle map through an
ordinary clean boot -- no save fixture, no debug launcher, no debug tools:

  * starter-danger-overlay-modern-{debug,release}          (QoL positive)
  * starter-danger-overlay-negative-modern-{debug,release}  (QoL negative)
  * starter-hook-clean-modern-release                       (hook positive)
  * starter-hook-clean-negative-modern-release              (hook negative)

The runtime values themselves are pinned by the committed fingerprints and
replayed by the Make gate expansion-modern-starter-runtime-check. What is
pinned here is the contract those fingerprints rest on: the routes really are
paired, the probes really are semantic scalars, the positives really do assert
a non-zero feature effect, and the negatives really do assert all-zero.
"""

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

QOL_POSITIVE = ["starter-danger-overlay-modern-debug",
                "starter-danger-overlay-modern-release"]
QOL_NEGATIVE = ["starter-danger-overlay-negative-modern-debug",
                "starter-danger-overlay-negative-modern-release"]
HOOK_POSITIVE = ["starter-hook-clean-modern-release"]
HOOK_NEGATIVE = ["starter-hook-clean-negative-modern-release"]
ALL = QOL_POSITIVE + QOL_NEGATIVE + HOOK_POSITIVE + HOOK_NEGATIVE

# The overlay probe's five u32 fields, in struct order.
_QOL_FIELDS = 5
# The mechanics probe's seven u32 fields, in struct order.
_HOOK_FIELDS = 7

_POINTER_BANDS = ((0x02000000, 0x0203FFFF),
                  (0x03000000, 0x03007FFF),
                  (0x08000000, 0x09FFFFFF))


def _load(name):
    return gba_playtest.parse_scenario_data(
        json.loads((SCENARIOS_DIR / (name + ".json")).read_text(encoding="utf-8")),
        str(SCENARIOS_DIR / (name + ".json")))


def _raw(name):
    return json.loads((SCENARIOS_DIR / (name + ".json")).read_text(encoding="utf-8"))


def _expectations(raw):
    out = []
    for cp in raw["checkpoints"]:
        for probe in cp["probes"]:
            if "expected" in probe:
                out.append((cp["name"], probe["address"], probe["size"],
                            int(probe["expected"], 16)))
    return out


def _u32_expectations(raw):
    return [e for e in _expectations(raw) if e[2] == 4]


class CleanRouteScenarioSchemaTests(unittest.TestCase):
    def test_all_scenarios_parse(self):
        for name in ALL:
            with self.subTest(scenario=name):
                scenario = _load(name)
                self.assertEqual(scenario.name, name)
                self.assertTrue(scenario.checkpoints)

    def test_every_scenario_has_a_committed_fingerprint(self):
        for name in ALL:
            with self.subTest(scenario=name):
                self.assertTrue((FINGERPRINTS_DIR / (name + ".json")).is_file(),
                                "missing fingerprint for %s" % name)

    def test_probes_are_semantic_scalars_never_pointers(self):
        for name in ALL:
            raw = _raw(name)
            for cpname, address, size, value in _expectations(raw):
                with self.subTest(scenario=name, checkpoint=cpname, address=address):
                    if size != 4:
                        continue
                    for low, high in _POINTER_BANDS:
                        self.assertFalse(
                            low <= value <= high,
                            "%s/%s expects pointer-like value 0x%08x"
                            % (name, cpname, value))

    def test_no_framebuffer_hashes(self):
        """Semantic scalars only -- never a framebuffer or timing oracle."""
        for name in ALL:
            raw = _raw(name)
            for cp in raw["checkpoints"]:
                with self.subTest(scenario=name, checkpoint=cp["name"]):
                    self.assertFalse(cp.get("framebuffer", False))
                    self.assertNotIn("sram_hash", cp)

    def test_positive_and_negative_share_the_same_clean_route_prefix(self):
        """A negative control is only meaningful on the paired route."""
        for positive, negative in (("starter-danger-overlay-modern-debug",
                                    "starter-danger-overlay-negative-modern-debug"),
                                   ("starter-danger-overlay-modern-release",
                                    "starter-danger-overlay-negative-modern-release"),
                                   ("starter-hook-clean-modern-release",
                                    "starter-hook-clean-negative-modern-release")):
            with self.subTest(pair=(positive, negative)):
                pos = [(f["start"], f["end"], tuple(f["keys"]))
                       for f in _raw(positive)["frames"]]
                neg = [(f["start"], f["end"], tuple(f["keys"]))
                       for f in _raw(negative)["frames"]]
                # Everything up to the first map-menu interaction (frame 3500)
                # is the shared clean-boot route.
                pos_prefix = [f for f in pos if f[0] < 3500]
                neg_prefix = [f for f in neg if f[0] < 3500]
                self.assertEqual(pos_prefix, neg_prefix)
                self.assertTrue(pos_prefix, "clean-route prefix must be non-empty")

    def test_route_uses_no_launcher_or_debug_key_combo(self):
        """SELECT+R is the debug Fast Boot launcher; it must not appear."""
        for name in ALL:
            for frame in _raw(name)["frames"]:
                with self.subTest(scenario=name, start=frame["start"]):
                    keys = set(frame["keys"])
                    self.assertFalse({"SELECT", "R"} <= keys,
                                     "%s uses the debug launcher combo" % name)
                    self.assertNotIn("SELECT", keys)

    def test_route_selects_normal_difficulty(self):
        """One DOWN on the Select Mode screen, and the probe that proves it."""
        for name in ALL:
            raw = _raw(name)
            with self.subTest(scenario=name):
                downs = [f for f in raw["frames"] if f["keys"] == ["DOWN"]
                         and f["start"] < 1500]
                self.assertEqual(len(downs), 1,
                                 "exactly one DOWN selects Normal on Select Mode")
                # PlaySt.config.controller (bit 5 of gPlaySt+0x42) is set for
                # Normal/Difficult and clear for Easy; PLAY_FLAG_HARD (0x40 in
                # chapterStateBits) separates Normal from Difficult.
                byte_expectations = {(a, v) for (_c, a, s, v) in _expectations(raw)
                                     if s == 1}
                self.assertTrue(any(v == 0x20 for (_a, v) in byte_expectations),
                                "%s must assert the Normal-mode config byte" % name)


class QolScenarioSemanticsTests(unittest.TestCase):
    def test_positive_asserts_the_full_overlay_lifecycle(self):
        for name in QOL_POSITIVE:
            raw = _raw(name)
            with self.subTest(scenario=name):
                by_cp = {}
                for cpname, _a, size, value in _expectations(raw):
                    if size == 4:
                        by_cp.setdefault(cpname, []).append(value)
                lifecycles = [v for v in by_cp.values() if len(v) == _QOL_FIELDS]
                self.assertEqual(len(lifecycles), len(raw["checkpoints"]))
                selects = [v[0] for v in lifecycles]
                displays = [v[1] for v in lifecycles]
                tiles = [v[2] for v in lifecycles]
                actives = [v[3] for v in lifecycles]
                cancels = [v[4] for v in lifecycles]
                self.assertEqual(sorted(set(selects)), [0, 1, 2],
                                 "menuSelectCount must go 0->1->2")
                self.assertEqual(sorted(set(displays)), [0, 1, 2],
                                 "dangerDisplayCount must go 0->1->2")
                self.assertEqual(sorted(set(cancels)), [0, 1, 2],
                                 "cancelReturnCount must go 0->1->2")
                self.assertIn(1, actives, "rangeGraphicsActive must reach 1")
                self.assertIn(0, actives, "rangeGraphicsActive must return to 0")
                self.assertEqual(sorted(set(tiles)), [0, 39],
                                 "both displays must generate exactly 39 tiles")
                # Monotonic non-decreasing counters -- no rewind, no reset.
                for series in (selects, displays, cancels):
                    self.assertEqual(series, sorted(series))

    def test_negative_asserts_every_overlay_field_stays_zero(self):
        for name in QOL_NEGATIVE:
            raw = _raw(name)
            with self.subTest(scenario=name):
                u32 = _u32_expectations(raw)
                self.assertEqual(len(u32), _QOL_FIELDS * len(raw["checkpoints"]))
                self.assertTrue(all(v == 0 for (_c, _a, _s, v) in u32),
                                "default-disabled build must stay all-zero")

    def test_debug_and_release_positives_assert_identical_semantics(self):
        debug = [v for (_c, _a, s, v) in _expectations(
            _raw("starter-danger-overlay-modern-debug")) if s == 4]
        release = [v for (_c, _a, s, v) in _expectations(
            _raw("starter-danger-overlay-modern-release")) if s == 4]
        self.assertEqual(debug, release,
                         "the overlay must behave identically in both configs")


class HookCleanScenarioSemanticsTests(unittest.TestCase):
    def test_positive_asserts_register_apply_and_bounded_delta(self):
        raw = _raw(HOOK_POSITIVE[0])
        groups = {}
        for cpname, _a, size, value in _expectations(raw):
            if size == 4:
                groups.setdefault(cpname, []).append(value)
        applied = [v for v in groups.values() if len(v) == _HOOK_FIELDS and v[0]]
        self.assertTrue(applied, "no checkpoint asserts the hook fired")
        for values in applied:
            (register_ok, register_err, apply_count, last_applied,
             last_delta, sample_trigger, last_result) = values
            self.assertEqual(register_ok, 1, "registered exactly once")
            self.assertEqual(register_err, 0, "no rejected registration")
            self.assertEqual(apply_count, 2, "applied once per combatant")
            self.assertEqual(last_applied, 1, "one registered mechanic iterated")
            self.assertEqual(last_delta, 1, "sample's bounded +1 defense delta")
            self.assertEqual(sample_trigger, 2, "full-HP guard fired for both")
            self.assertEqual(last_result, 0, "EXPANSION_MECHANICS_OK")

    def test_negative_asserts_every_hook_field_stays_zero(self):
        raw = _raw(HOOK_NEGATIVE[0])
        u32 = _u32_expectations(raw)
        self.assertEqual(len(u32), _HOOK_FIELDS * len(raw["checkpoints"]))
        self.assertTrue(all(v == 0 for (_c, _a, _s, v) in u32))

    def test_pair_resolves_the_same_real_battle(self):
        """Vanilla battle maths must be identical with the seam compiled out."""
        def hp_series(name):
            """(address, value) per checkpoint, in order; names differ by design."""
            return [(a, v) for (_c, a, s, v) in _expectations(_raw(name))
                    if s == 1]
        self.assertEqual(hp_series(HOOK_POSITIVE[0]), hp_series(HOOK_NEGATIVE[0]),
                         "the same clean route must resolve the same battle "
                         "and reach the same map state in both builds")

    def test_battle_actually_changed_a_units_hp(self):
        """Proves a genuine bout, not a faked counter write."""
        raw = _raw(HOOK_POSITIVE[0])
        seth_cur = [v for (_c, a, s, v) in _expectations(raw)
                    if s == 1 and a == "0x0202f9a7"]
        self.assertTrue(seth_cur, "Seth's curHP must be probed")
        self.assertGreater(max(seth_cur), min(seth_cur),
                           "Seth's HP must actually change across the bout")


if __name__ == "__main__":
    unittest.main()
