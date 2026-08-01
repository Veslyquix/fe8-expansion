"""Issue #18 sprint 7: `generated-data-check` cap-DAG closure regression.

Reported failure mode (branch-local): after `make generated-data-check`
(verify's `generated-data-check` gate, always run at the default,
unset-`FE8_ITEM_ID_CAP` cap) a *subsequent* `FE8_ITEM_ID_CAP=0xCE` item
gate could in principle "reuse the existing [build/generated/data]
target[s] by mtime and compile/read [a] stale header" -- i.e.
`build/generated/data/id_space_active.h` stuck at the default 0xCD/206
cap while a later, expanded-cap gate expects 0xCE/207 -- because
`generated-data-check`'s own recipe never referenced
`$(GENERATED_DATA_ITEM_CAP_STAMP)`, the one real, Make-tracked file every
other cap-aware rule (the grouped ACTIVE_OUTPUTS rule, every linked
table's `.c` rule) keys its own staleness on. `generated-data-check`
instead heals the ACTIVE surfaces (and the `items` table) via *direct*
python calls (`idspace active-check`, `check --table items`) that resolve
THIS invocation's own env cap and rewrite write-if-changed -- correct on
their own terms, but a structural asymmetry between "what the gate
actually does" and "what the Make dependency graph believes happened":
literally "cap missing from Make DAG/state".

Investigation summary (see the module docstring pattern of
scripts/modernize/tests/test_modern_itemexpansion_gate_order_race.py for
the established precedent): running the exact reported gate order for
real, in THIS repository's own artifact-rich `build/` tree (no
`clean`, no isolated `MODERN_BUILD_ROOT`) did not reproduce a stale
0xCD/206 header surviving into an expanded-cap gate -- `active-heal`'s
unconditional, env-resolved-cap probe (invoked from the stamp's own
FORCE recipe) already self-heals the surfaces regardless of the stamp's
prior content/mtime. But the named structural gap (the gate's own
recipe never touching the stamp) was real, so `generated_data.mk` now
declares `generated-data-check: $(GENERATED_DATA_ITEM_CAP_STAMP)` --
closing it for good, at the cost of one extra idempotent stamp-recipe
invocation, with no change to any gate's observable output.

This module is the durable regression: a fast, toolchain-independent
structural pin for the new prerequisite edge, plus a real (still
toolchain-independent -- `generated-data-check` never invokes
arm-none-eabi-gcc) integration test that drives the actual gate-relevant
default -> 0xCE -> 0xCE (warm) -> default (reverse) sequence against
THIS repository's real, shared, artifact-rich
`build/generated/data/` -- never a temp copy, never `clean` -- and
asserts the C header / JSON / Markdown surfaces agree at every
transition and that a same-cap warm rerun leaves every surface's mtime
untouched. A final, toolchain-gated (but still no libmGBA/ROM-boot
needed) tier compiles the real `data_items.o` object for both the
`debug` and `release` modern configs at the expanded cap and proves the
compiled object's own record count -- derived proportionally from its
linked data-section size, never a hardcoded byte count -- agrees with
whatever the header's ACTIVE_RECORD_COUNT says: the actual "gItem
expansion expects 207 but sees 206" consumer-side risk this issue names,
pinned without paying for a full ROM link/boot.
"""

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATED_DATA_MK = ROOT / "generated_data.mk"

OUT_DIR = ROOT / "build" / "generated" / "data"
HEADER = OUT_DIR / "id_space_active.h"
AUDIT_JSON = OUT_DIR / "id_space_active_audit.json"
AUDIT_MD = OUT_DIR / "id_space_active_audit.md"
STAMP = OUT_DIR / ".item_id_cap.stamp"

DEFAULT_CAP_HEX = "0xCD"
DEFAULT_RECORD_COUNT = 206
EXPANDED_CAP_HEX = "0xCE"
EXPANDED_RECORD_COUNT = 207


def _toolchain_available():
    return shutil.which("arm-none-eabi-gcc") is not None and shutil.which(
        "arm-none-eabi-size"
    ) is not None


def _run_generated_data_check(cap=None, timeout=180):
    """A real (not `-n`) `make generated-data-check` invocation against the
    actual repository build tree, with a clean baseline environment (no
    ambient FE8_ITEM_ID_CAP/MAKEFLAGS leaking in from the test runner)."""
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    if cap is None:
        env.pop("FE8_ITEM_ID_CAP", None)
    else:
        env["FE8_ITEM_ID_CAP"] = cap
    result = subprocess.run(
        ["make", "--no-print-directory", "generated-data-check"],
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )
    return result


def _header_defines():
    text = HEADER.read_text(encoding="utf-8")
    return dict(
        (m.group(1), m.group(2))
        for m in re.finditer(r"^#define\s+(\S+)\s+(\S+)\s*$", text, re.MULTILINE)
    )


def _mtimes():
    return {
        "header": HEADER.stat().st_mtime_ns,
        "json": AUDIT_JSON.stat().st_mtime_ns,
        "md": AUDIT_MD.stat().st_mtime_ns,
        "stamp": STAMP.stat().st_mtime_ns,
    }


class GeneratedDataCheckStampPrerequisiteTests(unittest.TestCase):
    """Fast, toolchain-independent structural pin for the DAG-closing edit:
    `generated-data-check` must list the item-cap stamp as a real
    prerequisite, not merely reach it through a direct, out-of-DAG python
    call inside its own recipe."""

    def setUp(self):
        self.text = GENERATED_DATA_MK.read_text(encoding="utf-8")

    def test_stamp_variable_is_defined(self):
        self.assertRegex(
            self.text,
            re.compile(r"^GENERATED_DATA_ITEM_CAP_STAMP\s*:=", re.MULTILINE),
            "GENERATED_DATA_ITEM_CAP_STAMP must stay a real make variable",
        )

    def test_generated_data_check_depends_on_the_cap_stamp(self):
        self.assertRegex(
            self.text,
            re.compile(
                r"^generated-data-check:\s*\$\(GENERATED_DATA_ITEM_CAP_STAMP\)\s*$",
                re.MULTILINE,
            ),
            "generated-data-check must declare "
            "$(GENERATED_DATA_ITEM_CAP_STAMP) as an ordinary prerequisite "
            "-- the gate's own recipe must not be the only thing in this "
            "repository that resolves/consumes FE8_ITEM_ID_CAP outside "
            "the Make dependency graph",
        )

    def test_stamp_recipe_still_self_heals_the_active_surfaces(self):
        # Pin that the stamp recipe's own inline self-heal calls (the
        # actual mechanism that already prevented the reported symptom
        # from reproducing) are not accidentally removed by some future
        # refactor now that the DAG edge above also exists.
        stamp_rule = re.search(
            r"^\$\(GENERATED_DATA_ITEM_CAP_STAMP\):.*?(?=^\S|\Z)",
            self.text,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(stamp_rule, "could not locate the stamp's own rule")
        body = stamp_rule.group(0)
        self.assertIn(".idspace active-heal", body)
        self.assertIn("check --table items", body)

    def test_dry_run_reaches_the_stamp_recipe(self):
        result = subprocess.run(
            ["make", "--no-print-directory", "-n", "generated-data-check"],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        self.assertIn(".item_id_cap.stamp", result.stdout)


class GeneratedDataCheckArtifactRichCapDagSequenceTests(unittest.TestCase):
    """Real integration coverage, run against THIS repository's actual,
    shared, artifact-rich build/generated/data/ -- never a temp copy,
    never `clean` -- for the gate-relevant, order-relevant subset of the
    11-gate `verify` sequence: default generated-data-check, an expanded
    (0xCE) probe, a same-cap warm rerun, then the reverse default gate.
    `generated-data-check` never invokes arm-none-eabi-gcc, so this whole
    class needs no cross-compiler toolchain."""

    @classmethod
    def setUpClass(cls):
        if not OUT_DIR.is_dir():
            raise unittest.SkipTest(
                "build/generated/data does not exist yet in this worktree "
                "(run `make generated-data-generate` first) -- this suite "
                "asserts on the real, existing artifact-rich tree and must "
                "never create it via `clean`/from scratch"
            )

    def tearDown(self):
        # Always leave the shared tree at the committed default cap, no
        # matter which assertion (if any) failed mid-sequence -- the same
        # "reverse default gate" step the task's own required sequence
        # ends on.
        _run_generated_data_check(cap=None)

    def _assert_active_summary(self, cap_hex, record_count):
        defines = _header_defines()
        self.assertEqual(defines.get("ITEM_ID_ACTIVE_CONFIGURED_CAP"), cap_hex)
        self.assertEqual(
            defines.get("ITEM_ID_ACTIVE_RECORD_COUNT"), str(record_count)
        )
        payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        item = next(d for d in payload["domains"] if d["key"] == "item")
        self.assertEqual(item["active_configured_cap"], int(cap_hex, 16))
        self.assertEqual(item["active_record_count"], record_count)
        md_text = AUDIT_MD.read_text(encoding="utf-8")
        want_row = "| item | {} | {} | {} | {} | {} |".format(
            "0x{:02X}".format(0xCD), DEFAULT_RECORD_COUNT,
            cap_hex, record_count,
            "no" if cap_hex == DEFAULT_CAP_HEX else "yes",
        )
        self.assertIn(
            want_row, md_text,
            "id_space_active_audit.md's item row disagrees with the header "
            "cap/count this transition just resolved",
        )

    def test_default_then_expanded_then_warm_then_reverse_default(self):
        # 1. Default gate (mirrors verify's own generated-data-check gate,
        #    which never sets FE8_ITEM_ID_CAP).
        result = _run_generated_data_check(cap=None)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self._assert_active_summary(DEFAULT_CAP_HEX, DEFAULT_RECORD_COUNT)

        # 2. Expanded-cap probe: header/JSON/MD must all move to 0xCE/207
        #    together, in this same shared tree, with no clean.
        result = _run_generated_data_check(cap=EXPANDED_CAP_HEX)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self._assert_active_summary(EXPANDED_CAP_HEX, EXPANDED_RECORD_COUNT)
        expanded_mtimes = _mtimes()

        # 3. Warm rerun at the SAME (expanded) cap must be a true no-op:
        #    every ACTIVE surface's mtime stays exactly where step 2 left
        #    it (write-if-changed all the way down -- no rebuild storm,
        #    no spurious touch).
        result = _run_generated_data_check(cap=EXPANDED_CAP_HEX)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self._assert_active_summary(EXPANDED_CAP_HEX, EXPANDED_RECORD_COUNT)
        self.assertEqual(
            _mtimes(), expanded_mtimes,
            "a same-cap warm generated-data-check rerun must not advance "
            "any ACTIVE surface's mtime",
        )

        # 4. Reverse default gate: a plain generated-data-check (no cap)
        #    must restore 0xCD/206, self-healing back down with no clean
        #    and no manual intervention.
        result = _run_generated_data_check(cap=None)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self._assert_active_summary(DEFAULT_CAP_HEX, DEFAULT_RECORD_COUNT)
        default_mtimes = _mtimes()

        # 5. Warm rerun at the restored default cap is equally a true
        #    no-op.
        result = _run_generated_data_check(cap=None)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self._assert_active_summary(DEFAULT_CAP_HEX, DEFAULT_RECORD_COUNT)
        self.assertEqual(
            _mtimes(), default_mtimes,
            "a warm default generated-data-check rerun must not advance "
            "any ACTIVE surface's mtime",
        )


@unittest.skipUnless(_toolchain_available(), "arm-none-eabi-gcc/-size not installed")
class ExpandedCapConsumerObjectAgreementTests(unittest.TestCase):
    """The actual consumer-side risk this issue names: a compiled
    data_items.o must carry exactly as many gItemData[] records as the
    ACTIVE header it was compiled against claims -- for BOTH the debug
    and release modern configs -- without paying for a full ROM
    link/boot. Kept deliberately cheap (a single reused-if-warm object
    compile per config/cap pair, never a full expansion-modern-rom), per
    this repository's own "keep cost reasonable" precedent (see
    test_modern_itemexpansion_gate_order_race.py's module docstring)."""

    CONFIGS = ("debug", "release")

    @classmethod
    def setUpClass(cls):
        if not OUT_DIR.is_dir():
            raise unittest.SkipTest(
                "build/generated/data does not exist yet in this worktree"
            )

    def tearDown(self):
        _run_generated_data_check(cap=None)
        for config in self.CONFIGS:
            self._build_object(config, cap=None)

    def _object_path(self, config):
        return ROOT / "build" / "expansion-modern" / config / "aapcs" / "src" / "data_items.o"

    def _build_object(self, config, cap):
        env = os.environ.copy()
        env.pop("MAKEFLAGS", None)
        if cap is None:
            env.pop("FE8_ITEM_ID_CAP", None)
        else:
            env["FE8_ITEM_ID_CAP"] = cap
        rel = str(self._object_path(config).relative_to(ROOT))
        result = subprocess.run(
            [
                "make", "--no-print-directory", rel,
                f"MODERN_CONFIG={config}", "MODERN_ABI=aapcs",
            ],
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        return result

    def _data_section_size(self, obj_path):
        result = subprocess.run(
            ["arm-none-eabi-size", str(obj_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        fields = result.stdout.splitlines()[1].split()
        return int(fields[1])  # data column

    def test_expanded_cap_object_record_count_matches_header_for_each_config(self):
        for config in self.CONFIGS:
            with self.subTest(config=config):
                self._build_object(config, cap=None)
                self._assert_active_summary_is(DEFAULT_CAP_HEX, DEFAULT_RECORD_COUNT)
                default_size = self._data_section_size(self._object_path(config))

                self._build_object(config, cap=EXPANDED_CAP_HEX)
                self._assert_active_summary_is(EXPANDED_CAP_HEX, EXPANDED_RECORD_COUNT)
                expanded_size = self._data_section_size(self._object_path(config))

                self.assertGreater(
                    expanded_size, default_size,
                    f"{config}: expanded-cap data_items.o must be larger "
                    f"than the default-cap object (207 records vs 206)",
                )
                # One record's size is content-addressed, never hardcoded:
                # derive it from the default build and assert the expanded
                # build's size is proportionally consistent with the
                # header's own ACTIVE_RECORD_COUNT -- i.e. the compiled
                # consumer object really does agree with 207, not merely
                # "bigger than before".
                self.assertEqual(default_size % DEFAULT_RECORD_COUNT, 0)
                record_size = default_size // DEFAULT_RECORD_COUNT
                self.assertEqual(
                    expanded_size, record_size * EXPANDED_RECORD_COUNT,
                    f"{config}: data_items.o's data section does not match "
                    f"{EXPANDED_RECORD_COUNT} records of size {record_size}",
                )

    def _assert_active_summary_is(self, cap_hex, record_count):
        defines = _header_defines()
        self.assertEqual(defines.get("ITEM_ID_ACTIVE_CONFIGURED_CAP"), cap_hex)
        self.assertEqual(
            defines.get("ITEM_ID_ACTIVE_RECORD_COUNT"), str(record_count)
        )


if __name__ == "__main__":
    unittest.main()
