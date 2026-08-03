"""
Issue #11 slice 1 host tests -- debug-tools registry, hotkey-collision
guards, one-entry-path enforcement, and scenario schema validation.

Where possible these tests compile and *execute* the real, unmodified
project sources (include/expansion_debugtools.h, src/debugtools_registry.c)
with a native host compiler rather than re-implementing or pattern-matching
their logic, so a regression in the actual registry/gate code is caught
here, not only on real hardware/emulator playtests. See
tools/gba-playtest/tests/c/ for the small stub/driver sources that make
this possible; those files are test-only and are never referenced by
modern.mk/Makefile.
"""

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INCLUDE_DIRS = [REPO_ROOT / "include", REPO_ROOT / "include" / "generated"]
C_FIXTURES_DIR = Path(__file__).resolve().parent / "c"
REGISTRY_SRC = REPO_ROOT / "src" / "debugtools_registry.c"
LAUNCHER_SRC = REPO_ROOT / "src" / "debugtools_launcher.c"
ACTIONS_SRC = REPO_ROOT / "src" / "debugtools_actions.c"
DIAG_SRC = REPO_ROOT / "src" / "debugtools_diag.c"
TOOLS_SRC = REPO_ROOT / "src" / "debugtools_tools.c"
GAMECONTROL_SRC = REPO_ROOT / "src" / "gamecontrol.c"
HEADER = REPO_ROOT / "include" / "expansion_debugtools.h"
TITLESCREEN_SRC = REPO_ROOT / "src" / "titlescreen.c"
PLAYERPHASE_SRC = REPO_ROOT / "src" / "playerphase.c"
PREP_SALLYCURSOR_SRC = REPO_ROOT / "src" / "prep_sallycursor.c"

CC = shutil.which("gcc") or shutil.which("cc")


def _strip_c_comments(text: str) -> str:
    """Removes /* ... */ and // ... C comments so structural (regex/grep)
    proofs below only ever match live code, never prose that merely
    *mentions* a banned symbol/pattern while explaining its absence."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def _skip_if_no_host_compiler():
    if CC is None:
        raise unittest.SkipTest("no host C compiler (gcc/cc) available")


def _include_flags():
    flags = []
    for d in INCLUDE_DIRS:
        flags += ["-I", str(d)]
    return flags


def _compile(work_dir: Path, src: Path, obj_name: str, defines=()):
    """Compiles a single source file to an object file with the host
    compiler. Returns (returncode, combined_output)."""
    obj = work_dir / obj_name
    cmd = [CC, "-c", "-w"] + _include_flags()
    for d in defines:
        cmd += ["-D", d]
    cmd += [str(src), "-o", str(obj)]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr, obj


def _link(work_dir: Path, objects, exe_name: str):
    exe = work_dir / exe_name
    cmd = [CC] + [str(o) for o in objects] + ["-o", str(exe)]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr, exe


def _run(exe: Path):
    proc = subprocess.run([str(exe)], capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _defined_symbol_names(obj: Path) -> set:
    nm = shutil.which("nm")
    if nm is None:
        raise unittest.SkipTest("no host 'nm' available")
    proc = subprocess.run([nm, str(obj)], capture_output=True, text=True)
    names = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        # "<addr> <type> <name>" for defined symbols; undefined entries use
        # "                 U <name>" (no address column).
        if len(parts) == 3 and parts[1] != "U":
            names.add(parts[2])
        elif len(parts) == 2 and parts[0] != "U":
            names.add(parts[1])
    return names


class DebugToolsRegistryHostTests(unittest.TestCase):
    """Compiles and executes the real src/debugtools_registry.c (enabled
    path) against tools/gba-playtest/tests/c/debugtools_registry_driver.c,
    proving capacity (max 9), deterministic append order, duplicate
    id/label rejection, invalid-action rejection, capacity-full rejection,
    and out-of-range NULL reads -- all through the exact public API
    (include/expansion_debugtools.h) contributor code uses.
    """

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def _build_and_run(self, tmp_path, driver_src, extra_objects_ok=True):
        work = Path(tmp_path)
        rc, out, registry_obj = _compile(
            work, REGISTRY_SRC, "registry_enabled.o",
            defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
        )
        self.assertEqual(rc, 0, f"compiling src/debugtools_registry.c (enabled) failed:\n{out}")

        rc, out, stubs_obj = _compile(work, C_FIXTURES_DIR / "debugtools_host_stubs.c", "stubs.o")
        self.assertEqual(rc, 0, f"compiling debugtools_host_stubs.c failed:\n{out}")

        rc, out, driver_obj = _compile(work, driver_src, "driver.o")
        self.assertEqual(rc, 0, f"compiling {driver_src.name} failed:\n{out}")

        rc, out, exe = _link(work, [registry_obj, stubs_obj, driver_obj], "test_exe")
        self.assertEqual(rc, 0, f"linking host registry test failed:\n{out}")

        rc, out = _run(exe)
        return rc, out

    def test_registry_capacity_order_and_errors(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._build_and_run(
                tmp, C_FIXTURES_DIR / "debugtools_registry_driver.c"
            )
            self.assertEqual(rc, 0, f"host registry test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_HOST_TEST: PASS", out)
            self.assertIn("DEBUGTOOLS_ACTION_MAX=9", out)
            self.assertIn("DEBUGTOOLS_HUB_MENU_SLOTS=11", out)

    def test_registry_id_and_label_validation(self):
        """Issue #11 closure: DebugTools_RegisterAction must explicitly
        reject id==0 (a reserved/uninitialized-looking sentinel) and an
        empty or over-long label, each with its own distinct, diagnosable
        DebugToolsResult code (DEBUGTOOLS_ERR_ID_INVALID/
        DEBUGTOOLS_ERR_LABEL_INVALID) -- never silently accepted, never
        conflated with the generic DEBUGTOOLS_ERR_INVALID_ACTION used for
        NULL action/label/callback pointers. Uses a dedicated, fresh-
        registry driver (rather than debugtools_registry_driver.c above,
        whose own registry is already at capacity by the time it reaches
        its rejection-path checks) so the boundary-accepted case
        (exactly DEBUGTOOLS_LABEL_MAX_LENGTH) can also be proven."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._build_and_run(
                tmp, C_FIXTURES_DIR / "debugtools_registry_label_validation_driver.c"
            )
            self.assertEqual(rc, 0, f"host label-validation test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_LABEL_VALIDATION_HOST_TEST: PASS", out)

    def test_registry_disabled_path_behavior_and_symbol_omission(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, registry_obj = _compile(
                work, REGISTRY_SRC, "registry_disabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=0"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_registry.c (disabled) failed:\n{out}")

            # Physical omission: the hub menu table and every hub-internal
            # static function must not exist as symbols at all in the
            # disabled translation unit -- this is the same evidence a
            # release ELF's `nm` output gives, but checkable on the host
            # without the arm-none-eabi toolchain.
            defined = _defined_symbol_names(registry_obj)
            forbidden = {
                "gDebugToolsHubMenuDef",
                "DebugToolsHub_BuildMenuItems",
                "DebugToolsHub_ShowDiagnostics",
                "DebugToolsHub_BackSelected",
                "DebugToolsHub_OnEnd",
            }
            leaked = forbidden & defined
            self.assertFalse(
                leaked,
                f"disabled build must physically omit hub internals; found: {leaked}",
            )
            # gDebugToolsProbe must still be linked in every build (the
            # release playtest scenario reads it directly by address).
            self.assertIn("gDebugToolsProbe", defined)

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_disabled_driver.c", "disabled_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_disabled_driver.c failed:\n{out}")

            rc, out, exe = _link(work, [registry_obj, driver_obj], "disabled_test_exe")
            self.assertEqual(rc, 0, f"linking disabled host test failed:\n{out}")

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"disabled-path host test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_DISABLED_HOST_TEST: PASS", out)


class DebugToolsHotkeyCollisionHostTests(unittest.TestCase):
    """Compiles small snippets against the real include/expansion_debugtools.h
    to prove its compile-time #error guards actually fire for both reserved
    soft-reset combos and for a zero mask, and that a legitimate override
    (and the untouched default) still compile cleanly."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def _compile_snippet(self, tmp_path, body: str):
        work = Path(tmp_path)
        src = work / "snippet.c"
        src.write_text(body)
        cmd = [CC, "-c", "-w"] + _include_flags() + [str(src), "-o", str(work / "snippet.o")]
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def test_default_mask_compiles(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._compile_snippet(
                tmp, '#include "expansion_debugtools.h"\nint main(void) { return 0; }\n'
            )
            self.assertEqual(rc, 0, f"the untouched default hotkey mask must compile cleanly:\n{out}")

    def test_zero_mask_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._compile_snippet(
                tmp,
                "#define FE8_EXPANSION_DEBUGTOOLS_HOTKEY_MASK (0)\n"
                '#include "expansion_debugtools.h"\n'
                "int main(void) { return 0; }\n",
            )
            self.assertNotEqual(rc, 0, "a zero hotkey mask must fail to compile")
            self.assertIn("must not be 0", out)

    def test_l_r_a_b_soft_reset_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._compile_snippet(
                tmp,
                "#define FE8_EXPANSION_DEBUGTOOLS_HOTKEY_MASK "
                "(L_BUTTON | R_BUTTON | A_BUTTON | B_BUTTON)\n"
                '#include "expansion_debugtools.h"\n'
                "int main(void) { return 0; }\n",
            )
            self.assertNotEqual(rc, 0, "the L+R+A+B soft-reset combo must be rejected at compile time")
            self.assertIn("L+R+A+B soft-reset combo", out)

    def test_a_b_select_start_soft_reset_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._compile_snippet(
                tmp,
                "#define FE8_EXPANSION_DEBUGTOOLS_HOTKEY_MASK "
                "(A_BUTTON | B_BUTTON | SELECT_BUTTON | START_BUTTON)\n"
                '#include "expansion_debugtools.h"\n'
                "int main(void) { return 0; }\n",
            )
            self.assertNotEqual(rc, 0, "the A+B+SELECT+START soft-reset combo must be rejected at compile time")
            self.assertIn("A+B+SELECT+START soft-reset combo", out)

    def test_legitimate_custom_mask_compiles(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # A_BUTTON | SELECT_BUTTON: distinct from the default map mask
            # (SELECT_BUTTON | L_BUTTON, issue #11 slice 2) and the default
            # prep mask (SELECT_BUTTON | B_BUTTON) that the header now also
            # cross-checks the title mask against -- L_BUTTON | SELECT_BUTTON
            # would collide with the map default and is deliberately not
            # used here.
            rc, out = self._compile_snippet(
                tmp,
                "#define FE8_EXPANSION_DEBUGTOOLS_HOTKEY_MASK (A_BUTTON | SELECT_BUTTON)\n"
                '#include "expansion_debugtools.h"\n'
                "int main(void) { return 0; }\n",
            )
            self.assertEqual(rc, 0, f"a non-colliding custom mask must compile cleanly:\n{out}")


class DebugToolsOneEntryPathTests(unittest.TestCase):
    """Structural (source-grep) proof that the title-screen hotkey has
    exactly one call site and one definition, matching the WHERE
    constraint that this slice adds exactly one global hub entry path."""

    def test_hotkey_check_has_exactly_one_call_site(self):
        call_sites = []
        for src in (REPO_ROOT / "src").glob("*.c"):
            text = src.read_text(encoding="utf-8", errors="replace")
            call_sites += [
                f"{src.name}:{i + 1}"
                for i, line in enumerate(text.splitlines())
                if re.search(r"\bDebugTools_TitleHotkeyCheck\s*\(", line)
                and "void DebugTools_TitleHotkeyCheck" not in line
            ]
        self.assertEqual(len(call_sites), 1, f"expected exactly one call site, found: {call_sites}")
        self.assertTrue(call_sites[0].startswith("titlescreen.c:"), call_sites)

    def test_hotkey_check_defined_exactly_once_per_config(self):
        # Two definitions live in the same file under #if/#else -- so the
        # *pattern* count is 2 (enabled + disabled bodies), never more;
        # that's the single supported source of truth for the entry path.
        text = REGISTRY_SRC.read_text(encoding="utf-8", errors="replace")
        defs = re.findall(r"^void DebugTools_TitleHotkeyCheck\(void\)$", text, flags=re.MULTILINE)
        self.assertEqual(len(defs), 2, "expected exactly one enabled + one disabled definition")

    def test_dormant_tools_untouched(self):
        for name in ("src/bmdebug.c", "src/uidebug.c", "src/menu_def.c"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("DebugTools_", text, f"{name} must stay untouched/unreachable per issue #11 slice 1 WHERE")


class DebugToolsScenarioSchemaTests(unittest.TestCase):
    """Validates the two new playtest scenarios against gba_playtest's own
    schema parser (the same validation `capture`/`verify` perform), and
    checks the debug/release scenarios assert complementary, non-trivial
    expectations (not just a placeholder pass-through)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPO_ROOT / "tools" / "gba-playtest"))
        global gba_playtest
        import gba_playtest  # noqa: F401 (imported for its side effect / module ref)

    def _load(self, name):
        import json
        path = REPO_ROOT / "tools" / "gba-playtest" / "scenarios" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        return gba_playtest.parse_scenario_data(data), data

    def test_debug_scenario_is_schema_valid(self):
        scenario, data = self._load("debugtools-hub-modern-debug.json")
        self.assertEqual(scenario.name, "debugtools-hub-modern-debug")
        self.assertEqual(len(data["checkpoints"]), 7)
        by_name = {c["name"]: c for c in data["checkpoints"]}
        self.assertIn("pre-launch", by_name)
        self.assertIn("chapter2-interactive-stable", by_name)

        def probe(checkpoint, address):
            for p in checkpoint["probes"]:
                if p["address"] == address:
                    return p
            self.fail(f"checkpoint {checkpoint['name']} does not probe {address}")

        stable = by_name["chapter2-interactive-stable"]
        self.assertEqual(probe(stable, "0x02031824")["expected"], "0x44424c31")  # launcherArmed magic
        self.assertEqual(probe(stable, "0x020210b2")["expected"], "0x02")  # CHAPTER_L_2
        self.assertEqual(probe(stable, "0x02031834")["expected"], "0x00000000")  # suppression cleared
        self.assertEqual(probe(stable, "0x02031838")["expected"], "0x00000001")  # playerPhaseObservedCount

    def test_release_scenario_is_schema_valid(self):
        scenario, data = self._load("debugtools-hub-modern-release.json")
        self.assertEqual(scenario.name, "debugtools-hub-modern-release")
        self.assertEqual(len(data["checkpoints"]), 7)

        # (1) No framebuffer oracle anywhere. The former frozen-screen hash
        # (d11078d0) was a vacuous compiled-out proof: a frozen screen
        # trivially matched a frozen-screen hash regardless of whether
        # debugtools linked, so the world-map UB fix (which unfroze the
        # screen) turned it into a false negative. Every checkpoint must now
        # capture relocation-independent semantic memory only.
        for checkpoint in data["checkpoints"]:
            self.assertFalse(
                checkpoint["framebuffer"],
                f"{checkpoint['name']} must not capture a framebuffer",
            )
            self.assertNotIn("expected_framebuffer_hash", checkpoint)

        by_name = {c["name"]: c for c in data["checkpoints"]}

        def probe(checkpoint, address):
            for p in checkpoint["probes"]:
                if p["address"] == address:
                    return p
            self.fail(f"checkpoint {checkpoint['name']} does not probe {address}")

        # (2) Compiled-out proof: the always-linked gDebugToolsProbe stays
        # all-zero at every checkpoint (hub never opens, no launcher armed,
        # the idle-timer setter never runs).
        zero_fields = (
            "0x02031504", "0x02031508", "0x0203150c", "0x02031510",
            "0x02031514", "0x02031518", "0x0203151c",
        )
        for checkpoint in data["checkpoints"]:
            for addr in zero_fields:
                self.assertEqual(
                    probe(checkpoint, addr)["expected"], "0x00000000",
                    f"{checkpoint['name']} gDebugToolsProbe {addr} must be all-zero",
                )

        # (3) Semantic progress/liveness: the inert START/A taps drive the
        # vanilla title -> new-game path into the live opening world-map
        # sequence. chapterIndex advances 0x00 (title) -> 0x10 (world map),
        # faction 0x00 -> 0x40 (NPC), map cursor 0x0000 -> 0x000e. That exact
        # transition is impossible on the pre-fix -O2 build, which locked
        # with chapterIndex stuck at 0x00 (frozen-vs-fixed capture evidence
        # is recorded in reports/issue6_foundation_evidence.md).
        title = by_name["title-idle-preboot-inert"]
        self.assertEqual(probe(title, "0x020210ae")["expected"], "0x00")
        self.assertEqual(probe(title, "0x020210af")["expected"], "0x00")
        self.assertEqual(probe(title, "0x02021100")["expected"], "0x0000")
        world_map = by_name["worldmap-intro-live-progress"]
        self.assertEqual(probe(world_map, "0x020210ae")["expected"], "0x10")
        self.assertEqual(probe(world_map, "0x020210af")["expected"], "0x40")
        self.assertEqual(probe(world_map, "0x02021100")["expected"], "0x000e")

        # (4) The progress scalar must actually CHANGE across the scenario
        # (liveness): a still/frozen build reads one constant value.
        chapter_values = {
            probe(c, "0x020210ae")["expected"] for c in data["checkpoints"]
        }
        self.assertEqual(
            chapter_values, {"0x00", "0x10"},
            "chapterIndex must transition title(0x00) -> world map(0x10) across checkpoints",
        )

    def test_debug_and_release_scenarios_use_identical_input_script(self):
        _, debug_data = self._load("debugtools-hub-modern-debug.json")
        _, release_data = self._load("debugtools-hub-modern-release.json")
        self.assertEqual(
            debug_data["frames"], release_data["frames"],
            "release must replay the exact same frame-for-frame input as debug "
            "to prove the hotkey (and the rest of the Chapter 2 tap sequence) "
            "has no debugtools effect, not merely a different script",
        )

    def test_debug_and_release_scenarios_probe_their_own_config_addresses(self):
        # gDebugToolsProbe's link-time BSS address legitimately differs
        # between debug and release (the hub/launcher code that precedes
        # it in link order is compiled out in release), so each scenario
        # must probe its own build's real address -- never the other
        # build's address, which would silently read unrelated BSS.
        _, debug_data = self._load("debugtools-hub-modern-debug.json")
        _, release_data = self._load("debugtools-hub-modern-release.json")
        debug_addrs = [p["address"] for p in debug_data["checkpoints"][0]["probes"]]
        release_addrs = [p["address"] for p in release_data["checkpoints"][0]["probes"]]
        self.assertNotEqual(debug_addrs, release_addrs)
        # Release reads its own gDebugToolsProbe base (0x02031504) and never
        # the debug build's (0x02031818); debug reads the opposite. This
        # survives the release scenario growing semantic progress probes.
        self.assertIn("0x02031504", release_addrs)
        self.assertNotIn("0x02031818", release_addrs)
        self.assertIn("0x02031818", debug_addrs)
        self.assertNotIn("0x02031504", debug_addrs)

    def test_debug_scenario_has_two_hotkey_pulses_before_the_select(self):
        """Review-fix regression: the reviewer reproduced hubOpenCount=2 by
        releasing and re-pressing SELECT+R while the hub remained open
        (pulses at 600-606 and 650-656). The scenario's frame script must
        replay that exact repeated-pulse shape, with the launcher-selecting
        A press occurring only after both pulses complete (the scenario
        also replays many further ordinary A/L/RIGHT/DOWN taps afterward,
        driving the real Chapter 2 flow -- those are not part of this
        reentrancy proof)."""
        _, data = self._load("debugtools-hub-modern-debug.json")
        hotkey_frames = [
            f for f in data["frames"]
            if set(f["keys"]) == {"SELECT", "R"}
        ]
        self.assertEqual(
            len(hotkey_frames), 2,
            "expected exactly two separate SELECT+R hotkey pulses (the reviewer's "
            "release-and-repress reproduction), found: {}".format(hotkey_frames),
        )
        # The two pulses must be fully separated (keys released in between)
        # so each one independently edge-triggers newKeys, matching the
        # reviewer's exact repro rather than one continuous hold.
        self.assertLess(hotkey_frames[0]["end"], hotkey_frames[1]["start"])
        a_frames = [f for f in data["frames"] if f["keys"] == ["A"] and f["start"] > hotkey_frames[1]["end"]]
        self.assertGreaterEqual(
            len(a_frames), 1,
            "expected at least the launcher-selecting A press strictly after both hotkey pulses",
        )
        self.assertEqual(
            a_frames[0]["start"], 700,
            "the launcher-selecting A press must be the first A press after both hotkey pulses",
        )

    def test_debug_scenario_proves_hub_open_count_stays_one_after_repeated_pulse(self):
        """The critical regression-proof checkpoint: hubOpenCount must be
        exactly 1 both right after the first pulse and again after the
        second (repeated) pulse -- never 2."""
        _, data = self._load("debugtools-hub-modern-debug.json")
        by_name = {c["name"]: c for c in data["checkpoints"]}
        self.assertIn("hub-opened-after-first-pulse", by_name)
        self.assertIn("hub-still-single-after-repeated-pulse", by_name)
        first = by_name["hub-opened-after-first-pulse"]
        second = by_name["hub-still-single-after-repeated-pulse"]
        self.assertLess(first["frame"], second["frame"])
        self.assertEqual(first["probes"][0]["expected"], "0x00000001")  # hubOpenCount
        self.assertEqual(
            second["probes"][0]["expected"], "0x00000001",
            "hubOpenCount must still read exactly 1 after the repeated hotkey pulse "
            "-- a value of 2 here would reproduce the reviewer's defect",
        )


class DebugToolsTimerFreezeTests(unittest.TestCase):
    """Structural and scenario-schema proof for the review-fix MEDIUM
    defect: Title_IDLE's proc->timer_idle (and its gDebugToolsProbe mirror)
    must freeze while the debug hub is active, rather than silently sailing
    past the vanilla `== 815` attract-mode-transition threshold."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPO_ROOT / "tools" / "gba-playtest"))
        global gba_playtest
        import gba_playtest  # noqa: F401

    def test_hub_active_check_precedes_timer_idle_increment(self):
        """Structural ordering proof: within Title_IDLE, the
        DebugTools_IsHubActive() check guarding the increment must appear
        (textually, and therefore control-flow-wise for this straight-line
        function body) before the proc->timer_idle++ statement it guards."""
        text = TITLESCREEN_SRC.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"void Title_IDLE\([^)]*\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "could not locate Title_IDLE's function body")
        body = match.group(1)

        guard_pos = body.find("DebugTools_IsHubActive")
        increment_pos = body.find("timer_idle++")
        self.assertNotEqual(guard_pos, -1, "Title_IDLE must reference DebugTools_IsHubActive()")
        self.assertNotEqual(increment_pos, -1, "Title_IDLE must still increment proc->timer_idle somewhere")
        self.assertLess(
            guard_pos, increment_pos,
            "the DebugTools_IsHubActive() guard must appear before the "
            "proc->timer_idle++ statement it protects, so the increment "
            "is actually skipped while the hub is active rather than the "
            "hub check merely gating unrelated logic afterward",
        )

    def test_timer_idle_increment_is_conditional_on_hub_inactive(self):
        """The increment must be reachable only when the hub is NOT
        active (a guard of `if (!DebugTools_IsHubActive())`), not merely
        textually preceded by an unrelated hub check."""
        text = TITLESCREEN_SRC.read_text(encoding="utf-8", errors="replace")
        match = re.search(
            r"if\s*\(\s*!\s*DebugTools_IsHubActive\(\)\s*\)\s*\{([^}]*timer_idle\+\+[^}]*)\}",
            text,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(
            match,
            "expected an `if (!DebugTools_IsHubActive()) { ... proc->timer_idle++ ... }` "
            "guard wrapping the idle-timer increment in Title_IDLE",
        )

    def _load(self, name):
        import json
        path = REPO_ROOT / "tools" / "gba-playtest" / "scenarios" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        return gba_playtest.parse_scenario_data(data), data

    def test_timer_freeze_scenario_is_schema_valid(self):
        scenario, data = self._load("debugtools-timer-freeze-modern-debug.json")
        self.assertEqual(scenario.name, "debugtools-timer-freeze-modern-debug")
        self.assertEqual(len(data["checkpoints"]), 3)

    def test_timer_freeze_scenario_proves_frozen_then_resumed(self):
        """The scenario JSON schema only supports exact-match expectations
        (no relational operators -- see gba_playtest.py's Probe.expected),
        so the freeze/resume proof's inequality reasoning must live here:
        parse the two 'frozen' checkpoints' titleIdleTimerSample values as
        integers and assert they are exactly equal (frozen while the hub
        is open, spanning the 815-frame threshold), then assert the final
        post-close checkpoint's value is strictly greater (resumed
        ticking after the hub closes)."""
        _, data = self._load("debugtools-timer-freeze-modern-debug.json")
        by_name = {c["name"]: c for c in data["checkpoints"]}
        for name in ("hub-open-early-sample", "hub-open-late-frozen", "hub-closed-resumed"):
            self.assertIn(name, by_name, f"missing expected checkpoint: {name}")

        def timer_value(checkpoint):
            for probe in checkpoint["probes"]:
                if probe["address"] == "0x02031828":
                    return int(probe["expected"], 16)
            self.fail(f"checkpoint {checkpoint['name']} does not probe titleIdleTimerSample")

        def hub_open_count(checkpoint):
            for probe in checkpoint["probes"]:
                if probe["address"] == "0x02031818":
                    return int(probe["expected"], 16)
            self.fail(f"checkpoint {checkpoint['name']} does not probe hubOpenCount")

        early = timer_value(by_name["hub-open-early-sample"])
        late = timer_value(by_name["hub-open-late-frozen"])
        resumed = timer_value(by_name["hub-closed-resumed"])

        self.assertEqual(
            early, late,
            "titleIdleTimerSample must be byte-for-byte identical across the "
            "two checkpoints spanning the 815-frame threshold while the hub "
            "remains open -- any difference means the timer advanced while blocked",
        )
        self.assertGreater(
            resumed, late,
            "titleIdleTimerSample must have increased after the hub is closed, "
            "proving idle-timer progress resumes rather than staying stuck forever",
        )

        # hubOpenCount must stay exactly 1 across opening, holding, and
        # closing the hub in this scenario -- opening once and closing it
        # must never require or trigger a second hub.
        for name in ("hub-open-early-sample", "hub-open-late-frozen", "hub-closed-resumed"):
            self.assertEqual(
                hub_open_count(by_name[name]), 1,
                f"hubOpenCount must stay 1 at checkpoint {name}",
            )

    def test_timer_freeze_scenario_holds_hub_open_across_815_threshold(self):
        """Sanity-check the scenario's own timing claim: the hub must open
        (via a single hotkey pulse) well before frame 1292 (empirically the
        frame at which a hub-free run's proc->timer_idle reaches 815, given
        the observed timer_idle == frame - 477 relationship while running
        freely) and must not be closed (no B press) until after it."""
        _, data = self._load("debugtools-timer-freeze-modern-debug.json")
        hotkey_frames = [f for f in data["frames"] if set(f["keys"]) == {"SELECT", "R"}]
        close_frames = [f for f in data["frames"] if f["keys"] == ["B"]]
        self.assertEqual(len(hotkey_frames), 1, "expected exactly one hotkey pulse opening the hub")
        self.assertEqual(len(close_frames), 1, "expected exactly one B press closing the hub")
        vanilla_815_frame = 815 + 477
        self.assertLess(hotkey_frames[0]["end"], vanilla_815_frame)
        self.assertGreater(close_frames[0]["start"], vanilla_815_frame)


class DebugToolsChapter2LaunchLifecycleHostTests(unittest.TestCase):
    """"Fast Boot: Chapter 2" lifecycle-safe launcher host tests. Compiles
    and executes the real, unmodified src/debugtools_launcher.c (enabled
    and disabled paths) against small host drivers
    (tools/gba-playtest/tests/c/debugtools_launcher_driver.c and
    debugtools_launcher_disabled_driver.c) to prove the pending-request/
    bootstrap-suppression lifecycle: arm-only (no proc calls), duplicate
    requests are explicit no-ops, GameControl-side consume is one-shot,
    and the whole subsystem is a harmless no-op when compiled out. The
    disabled/enabled driver stub files deliberately never define
    Proc_EndEach or any GameCtrl/BMapMain symbol -- if
    src/debugtools_launcher.c ever referenced one, these tests would fail
    to *link*, not just fail an assertion."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_launcher_pending_request_lifecycle_host_executed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, registry_obj = _compile(
                work, REGISTRY_SRC, "registry_enabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_registry.c (enabled) failed:\n{out}")

            rc, out, launcher_obj = _compile(
                work, LAUNCHER_SRC, "launcher_enabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_launcher.c (enabled) failed:\n{out}")

            rc, out, stubs_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_launcher_host_stubs.c", "launcher_stubs.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_launcher_host_stubs.c failed:\n{out}")

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_launcher_driver.c", "launcher_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_launcher_driver.c failed:\n{out}")

            rc, out, exe = _link(
                work, [registry_obj, launcher_obj, stubs_obj, driver_obj], "launcher_test_exe"
            )
            self.assertEqual(
                rc, 0,
                "linking host launcher lifecycle test failed -- an undefined reference here "
                f"would mean src/debugtools_launcher.c touches Proc_EndEach or GameCtrl/BMapMain "
                f"symbols that this driver deliberately never stubs:\n{out}",
            )

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"host launcher lifecycle test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_LAUNCHER_HOST_TEST: PASS", out)

    def test_launcher_disabled_path_is_noop(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, launcher_obj = _compile(
                work, LAUNCHER_SRC, "launcher_disabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=0"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_launcher.c (disabled) failed:\n{out}")

            # Physical omission: none of the hub-internal/proc-facing
            # symbols may exist at all in the disabled translation unit.
            defined = _defined_symbol_names(launcher_obj)
            forbidden = {
                "sChapter2LaunchPending",
                "sBootstrapSuppressionActive",
                "sBootstrapObserverTimer",
                "DebugToolsLauncher_FastBootChapter2",
                "sFastBootChapter2Action",
                "DebugToolsObserver_WaitForStablePlayerPhase",
                "DebugToolsObserver_OnEnd",
                "sDebugToolsBootstrapObserverScript",
                # Issue #11 closure: the second (Chapter 4 Prep) launcher's
                # own internals must be physically omitted too.
                "sChapter4PrepLaunchPending",
                "DebugToolsLauncher_FastBootChapter4Prep",
                "sFastBootChapter4PrepAction",
            }
            leaked = forbidden & defined
            self.assertFalse(
                leaked,
                f"disabled build must physically omit launcher internals; found: {leaked}",
            )

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_launcher_disabled_driver.c", "launcher_disabled_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_launcher_disabled_driver.c failed:\n{out}")

            # No Proc/registry stubs needed at all: the disabled path
            # never references gDebugToolsProbe, Proc_*, or
            # DebugTools_RegisterAction.
            rc, out, exe = _link(work, [launcher_obj, driver_obj], "launcher_disabled_test_exe")
            self.assertEqual(rc, 0, f"linking disabled host launcher test failed:\n{out}")

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"disabled-path host launcher test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_LAUNCHER_DISABLED_HOST_TEST: PASS", out)

    def test_launcher_never_references_gamectrl_or_proc_endeach(self):
        """Structural double-check (alongside the link-time proof above):
        src/debugtools_launcher.c must never mention Proc_EndEach,
        gProcScr_GameControl, or gProc_BMapMain anywhere in its *code*
        (comments documenting their deliberate absence are fine) -- the
        hub action only arms a pending request and closes the hub."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        for banned in ("Proc_EndEach", "gProcScr_GameControl", "gProc_BMapMain"):
            self.assertNotIn(
                banned, text,
                f"src/debugtools_launcher.c must never reference {banned} in code",
            )

    def test_arm_bootstrap_suppression_cleans_up_before_starting_fresh_observer(self):
        """Review fix (MEDIUM): DebugTools_ArmBootstrapSuppression's body
        must call DebugTools_CleanupBootstrapObserver() strictly before
        Proc_Start -- the fail-safe singleton property (never two
        concurrent observers, suppression never stuck on by a repeat arm)
        depends on cleanup always running first, not merely existing
        somewhere in the file."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(r"void DebugTools_ArmBootstrapSuppression\(void\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "could not locate DebugTools_ArmBootstrapSuppression's function body")
        body = match.group(1)

        cleanup_pos = body.find("DebugTools_CleanupBootstrapObserver(")
        start_pos = body.find("Proc_Start(")
        self.assertNotEqual(cleanup_pos, -1, "ArmBootstrapSuppression must call DebugTools_CleanupBootstrapObserver()")
        self.assertNotEqual(start_pos, -1, "ArmBootstrapSuppression must call Proc_Start(...) to start the observer")
        self.assertLess(
            cleanup_pos, start_pos,
            "cleanup must run before Proc_Start, so a repeat arm never leaves two observers alive",
        )

    def test_observer_script_installs_end_callback_as_its_first_entry(self):
        """The bootstrap observer's own ProcCmd script must install
        DebugToolsObserver_OnEnd via PROC_SET_END_CB as its first entry --
        that is what guarantees the callback fires on *every* termination
        path (Proc_Break's PROC_END fallthrough for any of the three
        conditions below, or an external Proc_End() call), not just the
        ones this file happens to also clear the flag from directly."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(
            r"struct ProcCmd CONST_DATA sDebugToolsBootstrapObserverScript\[\]\s*=\s*\{(.*?)\};",
            text,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "could not locate sDebugToolsBootstrapObserverScript's definition")
        entries = [e.strip() for e in match.group(1).split(",\n") if e.strip()]
        self.assertTrue(
            entries and entries[0].startswith("PROC_SET_END_CB(DebugToolsObserver_OnEnd)"),
            f"expected PROC_SET_END_CB(DebugToolsObserver_OnEnd) as the script's first entry, found: {entries[:1]}",
        )

    def test_observer_on_end_unconditionally_clears_suppression(self):
        """DebugToolsObserver_OnEnd must clear both the internal flag and
        the probe mirror unconditionally -- no `if` may guard either
        assignment, so calling it (from any termination path) can never
        leave suppression active."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(r"void DebugToolsObserver_OnEnd\(ProcPtr proc\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "could not locate DebugToolsObserver_OnEnd's function body")
        body = match.group(1)

        self.assertNotIn("if", body, "DebugToolsObserver_OnEnd must not contain any conditional")
        self.assertIn("sBootstrapSuppressionActive = 0", body)
        self.assertIn("gDebugToolsProbe.bootstrapSuppressionActive = 0", body)

    def test_observer_has_exactly_two_poll_termination_conditions_each_ending_via_proc_break(self):
        """DebugToolsObserver_WaitForStablePlayerPhase must check exactly
        two conditions in its own per-frame poll -- success
        (gProcScr_PlayerPhase) and the bounded timeout -- and every one of
        them must end the same way, via Proc_Break(proc): there must be
        no third, uncovered path through this function that leaves the
        proc (and therefore the suppression it owns) running forever.

        The third end condition (abandoned/returned-to-title) is
        deliberately NOT part of this poll: it is the separate,
        event-driven DebugTools_NotifyTitleScreenStarting, called from
        src/titlescreen.c the moment gProcScr_TitleScreen is actually
        (re)started, rather than polled via Proc_Find(gProcScr_TitleScreen)
        here -- see test_wait_for_stable_player_phase_never_polls_title_
        screen_via_proc_find below for why (FreeProcess never clears a
        freed proc's own proc_script field, so a Proc_Find-based poll for
        this condition cannot reliably distinguish a genuine re-start from
        a stale freed slot)."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(
            r"void DebugToolsObserver_WaitForStablePlayerPhase\(ProcPtr proc\)\s*\{(.*?)\n\}",
            text,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "could not locate DebugToolsObserver_WaitForStablePlayerPhase's function body")
        body = match.group(1)

        self.assertIn("Proc_Find(gProcScr_PlayerPhase)", body, "missing the success condition")
        self.assertIn("DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES", body, "missing the bounded timeout condition")

        proc_break_calls = len(re.findall(r"Proc_Break\s*\(\s*proc\s*\)", body))
        self.assertEqual(
            proc_break_calls, 2,
            f"expected exactly 2 Proc_Break(proc) calls (one per condition), found {proc_break_calls}",
        )

    def test_wait_for_stable_player_phase_never_polls_title_screen_via_proc_find(self):
        """DebugToolsObserver_WaitForStablePlayerPhase must never scan the
        proc tree for gProcScr_TitleScreen: FreeProcess (src/proc.c) never
        clears a freed proc's own proc_script field, so Proc_Find(
        gProcScr_TitleScreen) can return a stale, already-freed match --
        exactly the false positive that, in a real Chapter 2 boot, cleared
        suppression on the observer's very first tick (the just-ended real
        title screen proc's own freed slot) and let
        BmMain_SuspendBeforePhase's WriteSuspendSave fire mid-boot,
        corrupting/stalling the rest of Chapter 2's progression."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(
            r"void DebugToolsObserver_WaitForStablePlayerPhase\(ProcPtr proc\)\s*\{(.*?)\n\}",
            text,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "could not locate DebugToolsObserver_WaitForStablePlayerPhase's function body")
        body = match.group(1)

        self.assertNotIn("gProcScr_TitleScreen", body,
                          "the poll body must not reference gProcScr_TitleScreen at all")

    def test_notify_title_screen_starting_is_a_noop_unless_suppression_active(self):
        """DebugTools_NotifyTitleScreenStarting must guard its whole body
        behind `if (!sBootstrapSuppressionActive) return;` (or the
        logically equivalent early return) -- an ordinary title screen
        (re)start while no deterministic boot is pending must never touch
        observerTitleReturnCount or call cleanup."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(
            r"void DebugTools_NotifyTitleScreenStarting\(void\)\s*\{(.*?)\n\}",
            text,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "could not locate the enabled DebugTools_NotifyTitleScreenStarting body")
        body = match.group(1)

        self.assertIn("sBootstrapSuppressionActive", body,
                       "must check the suppression flag before doing anything")
        self.assertIn("DebugTools_CleanupBootstrapObserver()", body,
                       "must end the observer via the same fail-safe cleanup path as every other termination")
        self.assertIn("observerTitleReturnCount", body,
                       "must increment the title-return probe counter")

    def test_titlescreen_calls_notify_title_screen_starting_from_all_three_start_functions(self):
        """src/titlescreen.c's StartTitleScreen_WithMusic,
        StartTitleScreen_FlagFalse, and StartTitleScreen_FlagTrue are the
        only three places gProcScr_TitleScreen is ever (re)started as a
        blocking child of gProcScr_GameControl -- each one must call
        DebugTools_NotifyTitleScreenStarting so the bootstrap observer's
        abandoned-run detection is never silently bypassed by one of the
        three."""
        titlescreen_src = REPO_ROOT / "src" / "titlescreen.c"
        text = _strip_c_comments(titlescreen_src.read_text(encoding="utf-8", errors="replace"))

        for fn_name in ("StartTitleScreen_WithMusic", "StartTitleScreen_FlagFalse", "StartTitleScreen_FlagTrue"):
            match = re.search(
                r"void " + fn_name + r"\(ProcPtr parent\)\s*\{(.*?)\n\}",
                text,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(match, f"could not locate {fn_name}'s function body")
            body = match.group(1)
            self.assertIn("DebugTools_NotifyTitleScreenStarting()", body,
                           f"{fn_name} must call DebugTools_NotifyTitleScreenStarting()")

    def test_cleanup_bootstrap_observer_clears_flag_unconditionally_as_a_fail_safe(self):
        """DebugTools_CleanupBootstrapObserver must clear the suppression
        flag/probe mirror unconditionally, outside (after) the
        `if (observer != NULL) Proc_End(observer);` guard -- so even the
        (should-never-happen) case where Proc_Find fails to locate a live
        observer this module itself started still cannot leave
        suppression stuck on."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(r"void DebugTools_CleanupBootstrapObserver\(void\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "could not locate DebugTools_CleanupBootstrapObserver's function body")
        body = match.group(1)

        proc_end_guard = re.search(r"if\s*\(\s*observer\s*!=\s*NULL\s*\)\s*\n?\s*Proc_End\(observer\);", body)
        self.assertIsNotNone(proc_end_guard, "expected a guarded `if (observer != NULL) Proc_End(observer);`")

        clear_pos = body.find("sBootstrapSuppressionActive = 0")
        self.assertNotEqual(clear_pos, -1, "expected an unconditional suppression flag clear")
        self.assertGreater(
            clear_pos, proc_end_guard.end(),
            "the unconditional flag clear must appear after (outside) the observer!=NULL guard, "
            "not nested inside it",
        )

    def test_timeout_constant_matches_host_driver_copy(self):
        """The host driver (tools/gba-playtest/tests/c/
        debugtools_launcher_driver.c) keeps its own literal copy of
        DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES (the macro is
        deliberately not exposed via include/expansion_debugtools.h, so it
        cannot #include the real definition) -- this proves the two never
        silently drift apart, which would otherwise make the timeout host
        test loop below either not actually reach the real bound or waste
        cycles far past it."""
        source_text = LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace")
        source_match = re.search(
            r"#define\s+DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES\s+(\d+)", source_text
        )
        self.assertIsNotNone(source_match, "could not find the timeout constant in src/debugtools_launcher.c")

        driver_text = (C_FIXTURES_DIR / "debugtools_launcher_driver.c").read_text(
            encoding="utf-8", errors="replace"
        )
        driver_match = re.search(
            r"#define\s+DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES\s+(\d+)", driver_text
        )
        self.assertIsNotNone(driver_match, "could not find the mirrored timeout constant in the host driver")

        self.assertEqual(
            source_match.group(1), driver_match.group(1),
            "src/debugtools_launcher.c's real timeout bound and the host driver's mirrored copy "
            "must always match exactly",
        )

    def test_disabled_path_defines_cleanup_bootstrap_observer_as_a_plain_noop(self):
        """The #else (FE8_EXPANSION_DEBUGTOOLS_ENABLED disabled) branch
        must still define DebugTools_CleanupBootstrapObserver (the public
        API surface must be identical in both configs), but as a body-less
        no-op -- no proc/EWRAM-state reference of any kind."""
        text = _strip_c_comments(LAUNCHER_SRC.read_text(encoding="utf-8", errors="replace"))
        disabled_start = text.find("#else")
        self.assertNotEqual(disabled_start, -1, "could not locate the disabled (#else) branch")
        disabled_text = text[disabled_start:]

        match = re.search(r"void DebugTools_CleanupBootstrapObserver\(void\)\s*\{(.*?)\n\}", disabled_text, flags=re.DOTALL)
        self.assertIsNotNone(match, "disabled branch must still define DebugTools_CleanupBootstrapObserver")
        body = match.group(1)
        for banned in ("Proc_End", "Proc_Find", "Proc_Start", "sBootstrapSuppressionActive", "EWRAM_DATA"):
            self.assertNotIn(banned, body, f"disabled DebugTools_CleanupBootstrapObserver must not reference {banned}")

    def test_title_idle_defers_pending_request_check_until_hub_inactive(self):
        """Title_IDLE must check DebugTools_IsHubActive() (and return early
        while it's still active) strictly before it checks
        DebugTools_IsChapter2LaunchPending() -- the pending request must
        only ever be detected after the hub has fully closed, never while
        it's still open."""
        text = TITLESCREEN_SRC.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"void Title_IDLE\([^)]*\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "could not locate Title_IDLE's function body")
        body = match.group(1)

        hub_guard = re.search(r"if\s*\(\s*DebugTools_IsHubActive\(\)\s*\)\s*\n?\s*return;", body)
        pending_check_pos = body.find("DebugTools_IsChapter2LaunchPending")
        self.assertIsNotNone(
            hub_guard,
            "expected an `if (DebugTools_IsHubActive()) return;` early-out guard in Title_IDLE",
        )
        self.assertNotEqual(pending_check_pos, -1, "Title_IDLE must call DebugTools_IsChapter2LaunchPending()")
        self.assertLess(
            hub_guard.end(), pending_check_pos,
            "the hub-active early-out must appear before the pending-request check, so the "
            "request is only ever detected once the hub has fully closed",
        )

    def test_title_idle_pending_branch_never_synthesizes_input(self):
        """The pending-request branch in Title_IDLE must react with the
        same SetNextGameActionId/Proc_Break pair the ordinary A/START
        handling uses, and must never write to newKeys or any key-status
        buffer (no synthesized A/START keypress)."""
        text = TITLESCREEN_SRC.read_text(encoding="utf-8", errors="replace")
        match = re.search(
            r"if\s*\(\s*DebugTools_IsChapter2LaunchPending\(\)\s*\)\s*\{([^}]*)\}",
            text,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(
            match,
            "expected an `if (DebugTools_IsChapter2LaunchPending()) { ... }` branch in Title_IDLE",
        )
        body = match.group(1)
        self.assertIn("SetNextGameActionId", body)
        self.assertIn("Proc_Break", body)
        self.assertNotIn("newKeys", body)

    def test_gamecontrol_consumes_pending_launch_exactly_once_before_savemenu(self):
        """src/gamecontrol.c must call DebugTools_ConsumePendingChapter2Launch
        exactly once (a single call site), and that call must gate a
        branch which Proc_Goto's to the ordinary LGAMECTRL_EXEC_BM state
        (not a bespoke bypass state) and which appears, textually within
        GameControl_PostIntro, before the ordinary
        Proc_Goto(proc, LGAMECTRL_EXEC_SAVEMENU) ("StartSaveMenu") branch.
        (Issue #11 closure added a second, independent
        DebugTools_ConsumePendingChapter4PrepLaunch branch between this one
        and the SaveMenu fallback -- see
        test_gamecontrol_consumes_pending_ch4_prep_launch_exactly_once_before_savemenu
        below for its own, identically-shaped proof. This test's own slice
        is bounded at that second branch's own consume call so it keeps
        proving only the Chapter 2 branch's own property, not both
        combined.)"""
        text = GAMECONTROL_SRC.read_text(encoding="utf-8", errors="replace")
        consume_calls = [
            m.start() for m in re.finditer(r"DebugTools_ConsumePendingChapter2Launch\s*\(", text)
        ]
        self.assertEqual(
            len(consume_calls), 1,
            f"expected exactly one call to DebugTools_ConsumePendingChapter2Launch, found {len(consume_calls)}",
        )

        match = re.search(r"void GameControl_PostIntro\([^)]*\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "could not locate GameControl_PostIntro's function body")
        body = match.group(1)

        consume_pos = body.find("DebugTools_ConsumePendingChapter2Launch")
        ch4_consume_pos = body.find("DebugTools_ConsumePendingChapter4PrepLaunch")
        savemenu_pos = body.find("LGAMECTRL_EXEC_SAVEMENU")
        self.assertNotEqual(consume_pos, -1)
        self.assertNotEqual(ch4_consume_pos, -1)
        self.assertNotEqual(savemenu_pos, -1)
        self.assertLess(
            consume_pos, ch4_consume_pos,
            "the Chapter 2 pending-launch consume must appear before the Chapter 4 Prep one",
        )
        self.assertLess(
            ch4_consume_pos, savemenu_pos,
            "the Chapter 4 Prep pending-launch consume must appear before the ordinary SaveMenu branch",
        )

        # The Chapter 2 branch itself (from its own consume call to the
        # Chapter 4 Prep branch's own consume call) must target the
        # ordinary LGAMECTRL_EXEC_BM state, not a bespoke/extended bypass
        # variant such as LGAMECTRL_EXEC_BM_EXT.
        branch_text = body[consume_pos:ch4_consume_pos]
        goto_targets = re.findall(r"Proc_Goto\(\s*proc\s*,\s*(\w+)\s*\)", branch_text)
        self.assertEqual(
            goto_targets, ["LGAMECTRL_EXEC_BM"],
            f"the Chapter 2 boot branch must Proc_Goto exactly LGAMECTRL_EXEC_BM once, found: {goto_targets}",
        )

    def test_gamecontrol_consumes_pending_ch4_prep_launch_exactly_once_before_savemenu(self):
        """Mirrors test_gamecontrol_consumes_pending_launch_exactly_once_before_savemenu
        above for the issue #11 closure's second launcher
        (DebugTools_ConsumePendingChapter4PrepLaunch): exactly one call
        site, gating a branch that Proc_Goto's to the ordinary
        LGAMECTRL_EXEC_BM state, appearing after the Chapter 2 branch's own
        consume call and before the ordinary SaveMenu branch."""
        text = GAMECONTROL_SRC.read_text(encoding="utf-8", errors="replace")
        consume_calls = [
            m.start() for m in re.finditer(r"DebugTools_ConsumePendingChapter4PrepLaunch\s*\(", text)
        ]
        self.assertEqual(
            len(consume_calls), 1,
            f"expected exactly one call to DebugTools_ConsumePendingChapter4PrepLaunch, found {len(consume_calls)}",
        )

        match = re.search(r"void GameControl_PostIntro\([^)]*\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "could not locate GameControl_PostIntro's function body")
        body = match.group(1)

        ch4_consume_pos = body.find("DebugTools_ConsumePendingChapter4PrepLaunch")
        savemenu_pos = body.find("LGAMECTRL_EXEC_SAVEMENU")
        self.assertNotEqual(ch4_consume_pos, -1)
        self.assertNotEqual(savemenu_pos, -1)
        self.assertLess(
            ch4_consume_pos, savemenu_pos,
            "the Chapter 4 Prep pending-launch consume must appear before the ordinary SaveMenu branch",
        )

        branch_text = body[ch4_consume_pos:savemenu_pos]
        goto_targets = re.findall(r"Proc_Goto\(\s*proc\s*,\s*(\w+)\s*\)", branch_text)
        self.assertEqual(
            goto_targets, ["LGAMECTRL_EXEC_BM"],
            f"the Chapter 4 Prep boot branch must Proc_Goto exactly LGAMECTRL_EXEC_BM once, found: {goto_targets}",
        )

    def test_gamecontrol_chapter2_boot_never_bypasses_events_or_manually_loads_units(self):
        """The Chapter 2 boot branch in GameControl_PostIntro must never
        directly start/skip an event or battle map itself (StartBattleMap,
        CallEvent, StartEvent, any EventScr_* reference), and must never
        manipulate unit arrays by hand beyond the one documented
        NODE_CASTLE_FRELIA world-map placement -- the real
        EventScr_Ch2_BeginningScene / world-map / battle-map flow must run
        completely unmodified via the ordinary LGAMECTRL_EXEC_BM proc
        script. (See
        test_gamecontrol_ch4_prep_boot_never_bypasses_events_or_manually_loads_units
        below for the identically-shaped Chapter 4 Prep branch proof; this
        test's own slice ends at that branch's own consume call so the two
        branches are checked independently.)"""
        text = _strip_c_comments(GAMECONTROL_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(r"void GameControl_PostIntro\([^)]*\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)

        consume_pos = body.find("DebugTools_ConsumePendingChapter2Launch")
        ch4_consume_pos = body.find("DebugTools_ConsumePendingChapter4PrepLaunch")
        branch_text = body[consume_pos:ch4_consume_pos]

        for banned in ("StartBattleMap", "CallEvent", "StartEvent", "EventScr_"):
            self.assertNotIn(
                banned, branch_text,
                f"the Chapter 2 boot branch must never reference {banned} -- the real event/"
                "battle flow must run unmodified via the ordinary proc script",
            )

        # The only unit-array write in this branch must be the single
        # documented world-map location placement, never a direct
        # per-unit field write (position/state/items) that would amount
        # to manually placing battle-map units.
        unit_array_writes = re.findall(r"gUnitArray\w+\[[^\]]*\]\s*\.\s*(\w+)", branch_text)
        self.assertEqual(unit_array_writes, [], f"unexpected direct unit-array writes: {unit_array_writes}")
        gmdata_unit_writes = re.findall(r"gGMData\.units\[[^\]]*\]\s*\.\s*(\w+)", branch_text)
        self.assertEqual(
            gmdata_unit_writes, ["location"],
            f"the only gGMData.units[] field write in this branch must be 'location', found: {gmdata_unit_writes}",
        )

    def test_gamecontrol_ch4_prep_boot_never_bypasses_events_or_manually_loads_units(self):
        """Mirrors test_gamecontrol_chapter2_boot_never_bypasses_events_or_manually_loads_units
        above for the issue #11 closure's second launcher: the Chapter 4
        Prep boot branch must never directly start/skip an event or battle
        map itself, and its only gGMData.units[] field write must be the
        single documented NODE_BORGO_RIDGE world-map location placement."""
        text = _strip_c_comments(GAMECONTROL_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(r"void GameControl_PostIntro\([^)]*\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)

        ch4_consume_pos = body.find("DebugTools_ConsumePendingChapter4PrepLaunch")
        savemenu_pos = body.find("LGAMECTRL_EXEC_SAVEMENU")
        branch_text = body[ch4_consume_pos:savemenu_pos]

        for banned in ("StartBattleMap", "CallEvent", "StartEvent", "EventScr_"):
            self.assertNotIn(
                banned, branch_text,
                f"the Chapter 4 Prep boot branch must never reference {banned} -- the real event/"
                "battle flow must run unmodified via the ordinary proc script",
            )

        unit_array_writes = re.findall(r"gUnitArray\w+\[[^\]]*\]\s*\.\s*(\w+)", branch_text)
        self.assertEqual(unit_array_writes, [], f"unexpected direct unit-array writes: {unit_array_writes}")
        gmdata_unit_writes = re.findall(r"gGMData\.units\[[^\]]*\]\s*\.\s*(\w+)", branch_text)
        self.assertEqual(
            gmdata_unit_writes, ["location"],
            f"the only gGMData.units[] field write in this branch must be 'location', found: {gmdata_unit_writes}",
        )


class DebugToolsMapPrepHotkeyCollisionHostTests(unittest.TestCase):
    """Compiles small snippets against the real include/expansion_debugtools.h
    to prove the issue #11 slice 2 map-phase and prep-screen hotkey masks'
    compile-time #error guards fire for the same class of hazards as the
    title mask (zero, both soft-reset combos), for a collision against
    each phase's own bare R/L/START vanilla control, for a collision
    against the title mask, and (prep only) for a collision against the
    map mask -- and that a legitimate override of either still compiles
    cleanly."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def _compile_snippet(self, tmp_path, body: str):
        work = Path(tmp_path)
        src = work / "snippet.c"
        src.write_text(body)
        cmd = [CC, "-c", "-w"] + _include_flags() + [str(src), "-o", str(work / "snippet.o")]
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def _assert_rejected(self, tmp, define_line, expected_message_fragment):
        rc, out = self._compile_snippet(
            tmp,
            define_line + '\n#include "expansion_debugtools.h"\nint main(void) { return 0; }\n',
        )
        self.assertNotEqual(rc, 0, f"expected a compile-time rejection for:\n{define_line}\ngot:\n{out}")
        self.assertIn(expected_message_fragment, out)

    def _assert_compiles(self, tmp, define_line):
        rc, out = self._compile_snippet(
            tmp,
            define_line + '\n#include "expansion_debugtools.h"\nint main(void) { return 0; }\n',
        )
        self.assertEqual(rc, 0, f"expected a clean compile for:\n{define_line}\ngot:\n{out}")

    def test_default_map_and_prep_masks_compile(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._compile_snippet(
                tmp, '#include "expansion_debugtools.h"\nint main(void) { return 0; }\n'
            )
            self.assertEqual(rc, 0, f"the untouched default map/prep hotkey masks must compile cleanly:\n{out}")

    def test_map_mask_zero_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK (0)", "must not be 0"
            )

    def test_prep_mask_zero_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (0)", "must not be 0"
            )

    def test_map_mask_l_r_a_b_soft_reset_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp,
                "#define FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK (L_BUTTON | R_BUTTON | A_BUTTON | B_BUTTON)",
                "L+R+A+B soft-reset combo",
            )

    def test_prep_mask_a_b_select_start_soft_reset_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp,
                "#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (A_BUTTON | B_BUTTON | SELECT_BUTTON | START_BUTTON)",
                "A+B+SELECT+START soft-reset combo",
            )

    def test_map_mask_bare_r_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK (R_BUTTON)",
                "collides with bare R at the map phase",
            )

    def test_map_mask_bare_l_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK (L_BUTTON)",
                "collides with bare L at the map phase",
            )

    def test_map_mask_bare_start_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK (START_BUTTON)",
                "collides with bare START at the map phase",
            )

    def test_prep_mask_bare_r_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (R_BUTTON)",
                "collides with bare R at the prep screen",
            )

    def test_prep_mask_bare_l_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (L_BUTTON)",
                "collides with bare L at the prep screen",
            )

    def test_prep_mask_bare_start_collision_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (START_BUTTON)",
                "collides with bare START at the prep screen",
            )

    def test_map_mask_collides_with_title_mask_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # The default title mask is SELECT_BUTTON | R_BUTTON.
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK (SELECT_BUTTON | R_BUTTON)",
                "collides with the title-screen hub mask",
            )

    def test_prep_mask_collides_with_title_mask_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (SELECT_BUTTON | R_BUTTON)",
                "collides with the title-screen hub mask",
            )

    def test_prep_mask_collides_with_map_mask_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # The default map mask is SELECT_BUTTON | L_BUTTON.
            self._assert_rejected(
                tmp, "#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (SELECT_BUTTON | L_BUTTON)",
                "collides with the map-phase hub mask",
            )

    def test_legitimate_custom_map_mask_compiles(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_compiles(tmp, "#define FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK (SELECT_BUTTON | A_BUTTON)")

    def test_legitimate_custom_prep_mask_compiles(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._assert_compiles(tmp, "#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (SELECT_BUTTON | A_BUTTON)")


class DebugToolsMapPrepOneEntryPathTests(unittest.TestCase):
    """Structural (source-grep) proof that the map-phase and prep-screen
    hotkeys each have exactly one call site and one enabled + one disabled
    definition, matching the WHERE constraint that this slice adds
    exactly one global hub entry path per phase -- mirrors
    DebugToolsOneEntryPathTests for the title hotkey."""

    def _call_sites(self, func_name):
        call_sites = []
        for src in (REPO_ROOT / "src").glob("*.c"):
            text = src.read_text(encoding="utf-8", errors="replace")
            call_sites += [
                f"{src.name}:{i + 1}"
                for i, line in enumerate(text.splitlines())
                if re.search(rf"\b{re.escape(func_name)}\s*\(", line)
                and f"void {func_name}" not in line
            ]
        return call_sites

    def test_map_hotkey_check_has_exactly_one_call_site(self):
        call_sites = self._call_sites("DebugTools_MapHotkeyCheck")
        self.assertEqual(len(call_sites), 1, f"expected exactly one call site, found: {call_sites}")
        self.assertTrue(call_sites[0].startswith("playerphase.c:"), call_sites)

    def test_prep_hotkey_check_has_exactly_one_call_site(self):
        call_sites = self._call_sites("DebugTools_PrepHotkeyCheck")
        self.assertEqual(len(call_sites), 1, f"expected exactly one call site, found: {call_sites}")
        self.assertTrue(call_sites[0].startswith("prep_sallycursor.c:"), call_sites)

    def test_map_hotkey_check_defined_exactly_once_per_config(self):
        text = REGISTRY_SRC.read_text(encoding="utf-8", errors="replace")
        defs = re.findall(r"^void DebugTools_MapHotkeyCheck\(void\)$", text, flags=re.MULTILINE)
        self.assertEqual(len(defs), 2, "expected exactly one enabled + one disabled definition")

    def test_prep_hotkey_check_defined_exactly_once_per_config(self):
        text = REGISTRY_SRC.read_text(encoding="utf-8", errors="replace")
        defs = re.findall(r"^void DebugTools_PrepHotkeyCheck\(void\)$", text, flags=re.MULTILINE)
        self.assertEqual(len(defs), 2, "expected exactly one enabled + one disabled definition")

    def test_map_hotkey_check_is_the_first_statement_and_returns_while_hub_active(self):
        """PlayerPhase_MainIdle must call DebugTools_MapHotkeyCheck() as
        its first statement and immediately return while the hub is
        active, so a triggering key press can never also reach the
        vanilla map-phase controls in the same frame."""
        text = _strip_c_comments(PLAYERPHASE_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(r"\bPlayerPhase_MainIdle\s*\([^)]*\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "PlayerPhase_MainIdle definition not found")
        body = match.group(1)
        statements = [s.strip() for s in body.split(";") if s.strip()]
        self.assertGreaterEqual(len(statements), 1)
        self.assertIn("DebugTools_MapHotkeyCheck()", statements[0])
        self.assertIn("DebugTools_IsHubActive()", body[: body.find("DebugTools_MapHotkeyCheck") + 400])

    def test_prep_hotkey_check_is_the_first_statement_and_returns_while_hub_active(self):
        """PrepScreenProc_MapIdle must call DebugTools_PrepHotkeyCheck() as
        its first statement and immediately return while the hub is
        active."""
        text = _strip_c_comments(PREP_SALLYCURSOR_SRC.read_text(encoding="utf-8", errors="replace"))
        match = re.search(r"\bPrepScreenProc_MapIdle\s*\([^)]*\)\s*\{(.*?)\n\}", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "PrepScreenProc_MapIdle definition not found")
        body = match.group(1)
        statements = [s.strip() for s in body.split(";") if s.strip()]
        self.assertGreaterEqual(len(statements), 1)
        self.assertIn("DebugTools_PrepHotkeyCheck()", statements[0])
        self.assertIn("DebugTools_IsHubActive()", body[: body.find("DebugTools_PrepHotkeyCheck") + 400])

    def test_dormant_tools_still_untouched(self):
        for name in ("src/bmdebug.c", "src/uidebug.c", "src/menu_def.c"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("DebugTools_", text, f"{name} must stay untouched/unreachable per issue #11 slice 2 WHERE")


class DebugToolsWeatherFogActionsHostTests(unittest.TestCase):
    """Compiles and executes the real, unmodified src/debugtools_actions.c
    (enabled path) alongside the real src/debugtools_registry.c against
    tools/gba-playtest/tests/c/debugtools_actions_driver.c, proving:
    idempotent registration (id 2 "Weather", id 3 "Fog"), the combined
    registry capacity boundary stays at DEBUGTOOLS_ACTION_MAX (9) when
    counted alongside a simulated Chapter-2-launcher-sized filler set,
    exact MenuDef/MenuItemDef sentinel and callback wiring for both
    submenus (never a hand-rolled copy of the dormant src/bmdebug.c
    function pointers), DebugMonitor lifecycle ownership (started only if
    not already alive, ended only if this module started it, Fog never
    touches it at all), and the hub-reopen-on-Back behavior. Also proves
    the disabled build physically omits every adapter symbol down to the
    one no-op public entry point."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_actions_lifecycle_and_wiring_host_executed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, registry_obj = _compile(
                work, REGISTRY_SRC, "registry_enabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_registry.c (enabled) failed:\n{out}")

            rc, out, actions_obj = _compile(
                work, ACTIONS_SRC, "actions_enabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_actions.c (enabled) failed:\n{out}")

            rc, out, stubs_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_actions_host_stubs.c", "actions_stubs.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_actions_host_stubs.c failed:\n{out}")

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_actions_driver.c", "actions_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_actions_driver.c failed:\n{out}")

            rc, out, exe = _link(
                work, [registry_obj, actions_obj, stubs_obj, driver_obj], "actions_test_exe"
            )
            self.assertEqual(rc, 0, f"linking host Weather/Fog actions test failed:\n{out}")

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"host Weather/Fog actions test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_ACTIONS_HOST_TEST: PASS", out)

    def test_actions_disabled_path_is_noop_and_omits_every_symbol(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, actions_obj = _compile(
                work, ACTIONS_SRC, "actions_disabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=0"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_actions.c (disabled) failed:\n{out}")

            defined = _defined_symbol_names(actions_obj)
            forbidden = {
                "sWeatherAction",
                "sFogAction",
                "sWeatherMenuItemDefs",
                "sFogMenuItemDefs",
                "sWeatherMonitorStartedByUs",
                "gDebugToolsWeatherMenuDef",
                "gDebugToolsFogMenuDef",
                "DebugToolsActions_WeatherSelected",
                "DebugToolsActions_FogSelected",
                "DebugToolsWeather_BuildMenuItems",
                "DebugToolsFog_BuildMenuItems",
                "DebugToolsWeather_OnEnd",
                "DebugToolsFog_OnEnd",
                "DebugToolsWeather_StopMonitorIfOwned",
            }
            leaked = forbidden & defined
            self.assertFalse(
                leaked,
                f"disabled build must physically omit every adapter internal; found: {leaked}",
            )
            self.assertEqual(
                defined, {"DebugTools_RegisterWeatherFogActions"},
                f"disabled build must define exactly the one no-op public entry point, found: {defined}",
            )

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_actions_disabled_driver.c", "actions_disabled_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_actions_disabled_driver.c failed:\n{out}")

            # No menu/proc/hardware stub of any kind is linked here: an
            # undefined reference would mean the disabled path grew a
            # real dependency on StartOrphanMenu/Proc_*/DebugMenu_*.
            rc, out, exe = _link(work, [actions_obj, driver_obj], "actions_disabled_test_exe")
            self.assertEqual(rc, 0, f"linking disabled host Weather/Fog actions test failed:\n{out}")

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"disabled-path host Weather/Fog actions test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_ACTIONS_DISABLED_HOST_TEST: PASS", out)

    def test_actions_never_touch_dormant_files_or_persistent_apis(self):
        """Structural double-check (alongside the link-time proofs above):
        src/debugtools_actions.c must never mention SaveGame/Sram/write-
        save-block APIs, must never call Proc_Break/Proc_End/Proc_EndEach
        on anything other than the one documented ProcScr_DebugMonitor
        teardown, and must never reference bmdebug.c/uidebug.c/menu_def.c
        internals beyond the six documented onDraw/onSelected/onIdle
        dormant function pointers it is explicitly allowed to reuse by
        pointer."""
        text = _strip_c_comments(ACTIONS_SRC.read_text(encoding="utf-8", errors="replace"))

        for banned in ("SaveGame", "Sram", "WriteSaveBlock", "Proc_Break", "Proc_End(", "Proc_Delete"):
            self.assertNotIn(
                banned, text,
                f"src/debugtools_actions.c must never reference {banned} -- no persistent writes or "
                "foreign-proc teardown, only its own documented ProcScr_DebugMonitor Proc_EndEach",
            )

        proc_endeach_targets = re.findall(r"Proc_EndEach\(\s*(\w+)\s*\)", text)
        self.assertEqual(
            proc_endeach_targets, ["ProcScr_DebugMonitor"],
            f"the only Proc_EndEach target in this file must be ProcScr_DebugMonitor, found: {proc_endeach_targets}",
        )

    def test_actions_source_is_wired_into_both_builds(self):
        """The WHERE constraint requires the new source file to reach
        both the legacy (ldscript.txt) and modern (modern.mk) build
        outputs."""
        ldscript_text = (REPO_ROOT / "ldscript.txt").read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "src/debugtools_actions.o", ldscript_text,
            "ldscript.txt must link src/debugtools_actions.o into the legacy build",
        )

        modern_mk_text = (REPO_ROOT / "modern.mk").read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "src/debugtools_actions.c", modern_mk_text,
            "modern.mk must compile src/debugtools_actions.c into the modern build",
        )


class DebugToolsDiagHostTests(unittest.TestCase):
    """Compiles and executes the real, unmodified src/debugtools_diag.c
    (enabled path) against tools/gba-playtest/tests/c/debugtools_diag_driver.c,
    proving the bounded log ring (capacity, most-recent-first ordering,
    wraparound eviction, unbounded probe-mirrored running total) and the
    non-fatal assert record (never fires on a true condition, records
    exactly once per false condition, itself logs a ring entry) -- all
    through the exact public API (include/expansion_debugtools.h) any
    tool uses. A second test compiles the disabled path and proves both
    behavior (every entry point degrades to its disabled stub,
    DebugTools_GetLastAssertCode reads DEBUGTOOLS_ASSERT_NONE) and
    physical symbol omission -- the disabled object defines exactly the
    six no-op public entry points and no ring/assert-record storage at
    all."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_diag_ring_and_assert_record_host_executed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, diag_obj = _compile(
                work, DIAG_SRC, "diag_enabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_diag.c (enabled) failed:\n{out}")

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_diag_driver.c", "diag_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_diag_driver.c failed:\n{out}")

            rc, out, exe = _link(work, [diag_obj, driver_obj], "diag_test_exe")
            self.assertEqual(rc, 0, f"linking host diag test failed:\n{out}")

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"host diag test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_DIAG_HOST_TEST: PASS", out)

    def test_diag_disabled_path_is_noop_and_omits_every_symbol(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, diag_obj = _compile(
                work, DIAG_SRC, "diag_disabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=0"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_diag.c (disabled) failed:\n{out}")

            defined = _defined_symbol_names(diag_obj)
            forbidden = {"sLogRing", "sLogRingTotalWrites"}
            leaked = forbidden & defined
            self.assertFalse(leaked, f"disabled build must physically omit diag internals; found: {leaked}")
            self.assertEqual(
                defined,
                {
                    "DebugTools_LogEvent",
                    "DebugTools_GetLogCount",
                    "DebugTools_GetLogEntry",
                    "DebugTools_RecordAssertFailure",
                    "DebugTools_GetAssertFailureCount",
                    "DebugTools_GetLastAssertCode",
                },
                f"disabled build must define exactly the six no-op public entry points, found: {defined}",
            )

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_diag_disabled_driver.c", "diag_disabled_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_diag_disabled_driver.c failed:\n{out}")

            rc, out, exe = _link(work, [diag_obj, driver_obj], "diag_disabled_test_exe")
            self.assertEqual(
                rc, 0,
                "linking disabled host diag test failed -- an undefined reference here would mean "
                f"the disabled path grew a real dependency:\n{out}",
            )

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"disabled-path host diag test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_DIAG_DISABLED_HOST_TEST: PASS", out)

    def test_diag_source_is_wired_into_both_builds(self):
        ldscript_text = (REPO_ROOT / "ldscript.txt").read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "src/debugtools_diag.o", ldscript_text,
            "ldscript.txt must link src/debugtools_diag.o into the legacy build",
        )

        modern_mk_text = (REPO_ROOT / "modern.mk").read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "src/debugtools_diag.c", modern_mk_text,
            "modern.mk must compile src/debugtools_diag.c into the modern build",
        )

    def test_diag_never_touches_dormant_files_or_persistent_apis(self):
        """Structural double-check: the diagnostics foundation must never
        reference src/bmdebug.c/src/uidebug.c/src/menu_def.c internals or
        perform any persistent SRAM write -- it is a pure EWRAM
        ring/counter, matching the explicit "no mgba_printf, no
        interactive debugger, no arbitrary memory editor" non-goals."""
        text = _strip_c_comments(DIAG_SRC.read_text(encoding="utf-8", errors="replace"))
        for banned in ("DebugMenu_", "WriteSaveBlock", "WriteSuspendSave", "WriteGameSave", "mgba_printf", "Sram"):
            self.assertNotIn(banned, text, f"src/debugtools_diag.c must never reference {banned}")


class DebugToolsExtendedToolsHostTests(unittest.TestCase):
    """Compiles and executes the real, unmodified src/debugtools_tools.c
    (enabled path) together with the real src/debugtools_registry.c
    against tools/gba-playtest/tests/c/debugtools_tools_driver.c, proving:
    registration (ids 5-9, deterministic order, idempotent); each of the
    five tools' inspect semantics (state correctly sampled into
    gDebugToolsProbe); the four mutating tools' bounded confirm-submenu
    transactions (Unit heal, Convoy add, Flag toggle, RNG reseed) actually
    applying via the real engine helper functions (SetUnitHp/SetUnitStatus/
    AddItemToConvoy/SetFlag/ClearFlag/SetLCGRNValue/InitRN semantics,
    exercised through host-controllable fakes -- see
    debugtools_tools_host_stubs.c); and the invalid/edge-case input paths
    (missing unit target, full convoy) resulting in a safe, logged,
    assert-recorded no-op rather than any mutation or crash. The fifth
    tool (save-state) is proven read-only: no Confirm item exists at all.
    A second test compiles the disabled path and proves both behavior and
    physical symbol omission -- the disabled object defines exactly the
    one no-op DebugTools_RegisterExtendedToolActions() entry point and
    links clean with no engine/menu/hardware stub at all."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_extended_tools_lifecycle_host_executed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, registry_obj = _compile(
                work, REGISTRY_SRC, "registry_enabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_registry.c (enabled) failed:\n{out}")

            rc, out, tools_obj = _compile(
                work, TOOLS_SRC, "tools_enabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_tools.c (enabled) failed:\n{out}")

            # src/debugtools_tools.c calls into the real diagnostics
            # foundation (DebugTools_LogEvent/DebugTools_RecordAssertFailure) --
            # link the real, unmodified src/debugtools_diag.c alongside it,
            # not a stub, so this test proves genuine log-ring/assert-record
            # behavior for every tool's mutation, not just call wiring.
            rc, out, diag_obj = _compile(
                work, DIAG_SRC, "diag_enabled_for_tools.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=1"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_diag.c (enabled) failed:\n{out}")

            rc, out, stubs_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_tools_host_stubs.c", "tools_stubs.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_tools_host_stubs.c failed:\n{out}")

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_tools_driver.c", "tools_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_tools_driver.c failed:\n{out}")

            rc, out, exe = _link(
                work, [registry_obj, tools_obj, diag_obj, stubs_obj, driver_obj], "tools_test_exe"
            )
            self.assertEqual(rc, 0, f"linking host extended-tools test failed:\n{out}")

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"host extended-tools test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_TOOLS_HOST_TEST: PASS", out)

    def test_extended_tools_disabled_path_is_noop_and_omits_every_symbol(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rc, out, tools_obj = _compile(
                work, TOOLS_SRC, "tools_disabled.o",
                defines=["FE8_EXPANSION_DEBUGTOOLS_ENABLED=0"],
            )
            self.assertEqual(rc, 0, f"compiling src/debugtools_tools.c (disabled) failed:\n{out}")

            defined = _defined_symbol_names(tools_obj)
            self.assertEqual(
                defined, {"DebugTools_RegisterExtendedToolActions"},
                f"disabled build must define exactly the one no-op public entry point, found: {defined}",
            )

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "debugtools_tools_disabled_driver.c", "tools_disabled_driver.o"
            )
            self.assertEqual(rc, 0, f"compiling debugtools_tools_disabled_driver.c failed:\n{out}")

            rc, out, exe = _link(work, [tools_obj, driver_obj], "tools_disabled_test_exe")
            self.assertEqual(
                rc, 0,
                "linking disabled host extended-tools test failed -- an undefined reference here "
                f"would mean the disabled path grew a real engine/menu/hardware dependency:\n{out}",
            )

            rc, out = _run(exe)
            self.assertEqual(rc, 0, f"disabled-path host extended-tools test failed:\n{out}")
            self.assertIn("DEBUGTOOLS_TOOLS_DISABLED_HOST_TEST: PASS", out)

    def test_extended_tools_never_touch_dormant_files_or_persistent_apis(self):
        """Structural double-check: src/debugtools_tools.c must never
        reference src/bmdebug.c/src/uidebug.c/src/menu_def.c internals,
        and must never perform a raw SRAM/save write -- every mutation
        goes through an ordinary EWRAM runtime engine helper
        (SetUnitHp/AddItemToConvoy/SetFlag/SetLCGRNValue etc.), never a
        save-block/SRAM API."""
        text = _strip_c_comments(TOOLS_SRC.read_text(encoding="utf-8", errors="replace"))
        for banned in ("DebugMenu_", "WriteSaveBlock", "WriteSuspendSave", "WriteGameSave", "BuildCurrentExpansionSaveMeta"):
            self.assertNotIn(banned, text, f"src/debugtools_tools.c must never reference {banned}")

    def test_extended_tools_source_is_wired_into_both_builds(self):
        ldscript_text = (REPO_ROOT / "ldscript.txt").read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "src/debugtools_tools.o", ldscript_text,
            "ldscript.txt must link src/debugtools_tools.o into the legacy build",
        )

        modern_mk_text = (REPO_ROOT / "modern.mk").read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "src/debugtools_tools.c", modern_mk_text,
            "modern.mk must compile src/debugtools_tools.c into the modern build",
        )


class DebugToolsMapPrepScenarioSchemaTests(unittest.TestCase):
    """Validates the slice 2 map/prep playtest scenarios (map-phase debug
    hub entry proved live against a real interactive Chapter 2, plus
    release mirrors for both the map and prep hotkeys) against
    gba_playtest's own schema parser -- the same validation `capture`/
    `verify` perform -- and checks each scenario's non-trivial claims,
    mirroring DebugToolsScenarioSchemaTests' pattern for the slice 1 title
    hub scenarios."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPO_ROOT / "tools" / "gba-playtest"))
        global gba_playtest
        import gba_playtest  # noqa: F401 (imported for its side effect / module ref)

    def _load(self, name):
        import json
        path = REPO_ROOT / "tools" / "gba-playtest" / "scenarios" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        return gba_playtest.parse_scenario_data(data), data

    def test_map_debug_scenario_is_schema_valid(self):
        scenario, data = self._load("debugtools-map-hub-modern-debug.json")
        self.assertEqual(scenario.name, "debugtools-map-hub-modern-debug")
        self.assertEqual(len(data["checkpoints"]), 13)
        by_name = {c["name"]: c for c in data["checkpoints"]}
        for expected_name in (
            "map-hub-opened-after-first-pulse",
            "map-hub-still-single-after-repeat-pulse",
            "weather-cycled-twice",
            "fog-toggled",
            "map-hub-closed-final",
            "map-remains-interactive",
        ):
            self.assertIn(expected_name, by_name, f"missing checkpoint {expected_name!r}")

    def test_map_debug_scenario_reuses_the_hub_scenarios_frame_prefix(self):
        """The map scenario must build on top of the already-verified
        Chapter 2 launch sequence (debugtools-hub-modern-debug.json),
        not a fresh/independent boot script, so the interactive map
        state it probes is proven by the same reentrancy-safe launch
        path as slice 1."""
        _, map_data = self._load("debugtools-map-hub-modern-debug.json")
        _, hub_data = self._load("debugtools-hub-modern-debug.json")
        prefix_len = len([f for f in hub_data["frames"] if f["end"] <= 14164])
        self.assertGreater(prefix_len, 0)
        self.assertEqual(
            map_data["frames"][:prefix_len], hub_data["frames"][:prefix_len],
            "map scenario's frame prefix (frames ending <= 14164) must be byte-for-byte "
            "identical to debugtools-hub-modern-debug.json's own frames",
        )

    def test_map_debug_scenario_proves_map_hotkey_pulses_do_not_double_open(self):
        _, data = self._load("debugtools-map-hub-modern-debug.json")
        by_name = {c["name"]: c for c in data["checkpoints"]}
        first = by_name["map-hub-opened-after-first-pulse"]
        second = by_name["map-hub-still-single-after-repeat-pulse"]

        def probe(checkpoint, address):
            for p in checkpoint["probes"]:
                if p["address"] == address:
                    return p
            self.fail(f"checkpoint {checkpoint['name']} does not probe {address}")

        # hubOpenCount must read 2 both times (1 from the title-hub launch
        # sequence already replayed in the shared prefix, +1 from this
        # scenario's own first map-hotkey pulse) -- never 3.
        self.assertEqual(probe(first, "0x02031818")["expected"], "0x00000002")
        self.assertEqual(probe(second, "0x02031818")["expected"], "0x00000002")

    def test_map_debug_scenario_proves_map_remains_interactive_after_hub_closes(self):
        """Central DONE criterion: after the hub fully closes, the player
        map must still respond to ordinary cursor input -- proven here by
        the cursor's x coordinate advancing from 0x06 to 0x07 on the final
        RIGHT press, with sHubActive staying 0 and hubOpenCount unchanged
        (4) across both checkpoints."""
        _, data = self._load("debugtools-map-hub-modern-debug.json")
        by_name = {c["name"]: c for c in data["checkpoints"]}
        closed = by_name["map-hub-closed-final"]
        interactive = by_name["map-remains-interactive"]

        def probe(checkpoint, address):
            for p in checkpoint["probes"]:
                if p["address"] == address:
                    return p
            self.fail(f"checkpoint {checkpoint['name']} does not probe {address}")

        self.assertEqual(probe(closed, "0x02031614")["expected"], "0x00000000")  # sHubActive
        self.assertEqual(probe(interactive, "0x02031614")["expected"], "0x00000000")
        self.assertEqual(probe(closed, "0x02031818")["expected"], probe(interactive, "0x02031818")["expected"])
        self.assertEqual(probe(closed, "0x02021104")["expected"], "0x06")  # cursor x, before final RIGHT
        self.assertEqual(probe(interactive, "0x02021104")["expected"], "0x07")  # cursor x, after final RIGHT

    def _assert_release_worldmap_negative(self, data, zero_fields):
        """Shared invariant for the map/prep release mirrors: no framebuffer
        oracle, all-zero gDebugToolsProbe compiled-out fields, and the live
        opening world-map progress scalars (which read 0x00 on the pre-fix
        frozen build)."""
        def probe(checkpoint, address):
            for p in checkpoint["probes"]:
                if p["address"] == address:
                    return p
            self.fail(f"checkpoint {checkpoint['name']} does not probe {address}")

        for checkpoint in data["checkpoints"]:
            self.assertFalse(
                checkpoint["framebuffer"],
                f"{checkpoint['name']} must not capture a framebuffer",
            )
            self.assertNotIn("expected_framebuffer_hash", checkpoint)
            for addr in zero_fields:
                self.assertEqual(
                    probe(checkpoint, addr)["expected"], "0x00000000",
                    f"{checkpoint['name']} gDebugToolsProbe {addr} must be all-zero",
                )
            # Live world-map progress reached (0x00 on the frozen pre-fix
            # build): chapterIndex 0x10, faction 0x40 (NPC), map cursor 0x0e.
            # Held constant across the appended hotkey tail == the hotkey is
            # inert (never opens a hub / never changes game state).
            self.assertEqual(probe(checkpoint, "0x020210ae")["expected"], "0x10")
            self.assertEqual(probe(checkpoint, "0x020210af")["expected"], "0x40")
            self.assertEqual(probe(checkpoint, "0x02021100")["expected"], "0x000e")

    def test_map_release_scenario_is_schema_valid(self):
        scenario, data = self._load("debugtools-map-hub-modern-release.json")
        self.assertEqual(scenario.name, "debugtools-map-hub-modern-release")
        self.assertEqual(len(data["checkpoints"]), 4)
        self._assert_release_worldmap_negative(
            data,
            zero_fields=(
                "0x02031504", "0x02031508", "0x0203150c", "0x02031510",
                "0x02031514", "0x02031518", "0x0203151c",
            ),
        )

    def test_prep_release_scenario_is_schema_valid(self):
        scenario, data = self._load("debugtools-prep-hub-modern-release.json")
        self.assertEqual(scenario.name, "debugtools-prep-hub-modern-release")
        self.assertEqual(len(data["checkpoints"]), 4)
        # The prep mirror additionally proves the prep-specific launcher
        # fields (pendingCh4PrepLaunchRequest / ch4PrepLauncherArmed /
        # ch4PrepLaunchRequestConsumedCount / prepScreenObservedCount) are
        # all-zero: the SELECT+B hotkey and its Ch4-Prep launcher are
        # compiled out. This release input never reaches a real prep screen
        # (documented honest scope), only the live opening world map.
        self._assert_release_worldmap_negative(
            data,
            zero_fields=(
                "0x02031504", "0x02031508", "0x0203150c", "0x02031510",
                "0x02031534", "0x02031538", "0x0203153c", "0x02031540",
            ),
        )

    def test_map_and_prep_release_scenarios_reuse_the_hub_release_scenarios_frames(self):
        """Both release mirrors must replay debugtools-hub-modern-release.json's
        own exact, already-verified 259-frame input script as their prefix
        (not the debug scenario's frames, and not a fresh script), per the
        documented rationale that the debug-launcher hotkey never fires in
        a release build."""
        _, hub_release_data = self._load("debugtools-hub-modern-release.json")
        prefix = hub_release_data["frames"]
        for name in (
            "debugtools-map-hub-modern-release.json",
            "debugtools-prep-hub-modern-release.json",
        ):
            _, data = self._load(name)
            self.assertEqual(
                data["frames"][: len(prefix)], prefix,
                f"{name} must replay debugtools-hub-modern-release.json's frames verbatim as its prefix",
            )
            self.assertGreater(
                len(data["frames"]), len(prefix),
                f"{name} must append its own hotkey tail after the shared prefix",
            )

    def test_map_and_prep_release_scenarios_use_distinct_hotkey_masks(self):
        """The map release mirror must exercise SELECT+L and the prep
        release mirror must exercise SELECT+B -- the two configured,
        mutually distinct masks -- not the same key combination."""
        _, hub_release_data = self._load("debugtools-hub-modern-release.json")
        prefix_len = len(hub_release_data["frames"])

        _, map_data = self._load("debugtools-map-hub-modern-release.json")
        map_tail = map_data["frames"][prefix_len:]
        map_hotkey_frames = [f for f in map_tail if set(f["keys"]) == {"SELECT", "L"}]
        self.assertEqual(len(map_hotkey_frames), 2)

        _, prep_data = self._load("debugtools-prep-hub-modern-release.json")
        prep_tail = prep_data["frames"][prefix_len:]
        prep_hotkey_frames = [f for f in prep_tail if set(f["keys"]) == {"SELECT", "B"}]
        self.assertEqual(len(prep_hotkey_frames), 2)

    def test_release_negatives_forbid_any_framebuffer_and_require_semantic_probes(self):
        """Standing guard (issue #6 sprint 1 gate remediation) replacing the
        former "stay at the frozen release frame" test.

        The three debugtools release negatives -- hub, map, prep -- must
        never again use a framebuffer oracle. The old frozen-screen hash
        (d11078d0) vacuously "passed" only because the world-map UB froze
        the screen, so a frozen-screen hash matched whether or not
        debugtools was compiled out; once the Proc_FindNext NULL-guard fix
        unfroze the screen it became a false negative. Each release scenario
        AND its fingerprint must instead carry: (a) zero framebuffer
        captures, (b) all-zero gDebugToolsProbe fields (compiled-out proof),
        and (c) relocation-independent semantic progress probes -- with the
        hub scenario exhibiting an actual chapterIndex change (liveness). No
        4-byte probe may hold a pointer-range value."""
        import json

        release = (
            "debugtools-hub-modern-release.json",
            "debugtools-map-hub-modern-release.json",
            "debugtools-prep-hub-modern-release.json",
        )
        pointer_ranges = (
            (0x02000000, 0x0203FFFF), (0x03000000, 0x03007FFF),
            (0x08000000, 0x0DFFFFFF), (0x0E000000, 0x0E00FFFF),
        )

        def in_pointer_range(value):
            return any(lo <= value <= hi for lo, hi in pointer_ranges)

        for name in release:
            _, sdata = self._load(name)
            fpath = REPO_ROOT / "tools" / "gba-playtest" / "fingerprints" / name
            fdata = json.loads(fpath.read_text(encoding="utf-8"))

            # (a) No framebuffer anywhere -- scenario or fingerprint.
            for checkpoint in sdata["checkpoints"]:
                self.assertFalse(
                    checkpoint["framebuffer"],
                    f"{name}:{checkpoint['name']} must not capture a framebuffer",
                )
                self.assertNotIn("expected_framebuffer_hash", checkpoint)
            for checkpoint in fdata["checkpoints"]:
                self.assertNotIn(
                    "framebuffer_hash", checkpoint,
                    f"{name} fingerprint {checkpoint['name']!r} must not carry a framebuffer hash",
                )

            # (b) all-zero gDebugToolsProbe base + (c) semantic scalar,
            # per checkpoint; and no pointer-valued 4-byte probe.
            for checkpoint in sdata["checkpoints"]:
                addrs = {p["address"]: p for p in checkpoint["probes"]}
                for base in ("0x02031504", "0x02031508", "0x0203150c", "0x02031510"):
                    self.assertIn(base, addrs, f"{name}:{checkpoint['name']} missing {base}")
                    self.assertEqual(addrs[base]["expected"], "0x00000000")
                semantic = [
                    a for a in addrs
                    if a in ("0x020210ae", "0x020210af", "0x020210bb", "0x02021100")
                ]
                self.assertTrue(
                    semantic,
                    f"{name}:{checkpoint['name']} must carry semantic progress probes, "
                    "not a framebuffer-only oracle",
                )
                for p in checkpoint["probes"]:
                    if p["size"] >= 4 and p.get("expected"):
                        self.assertFalse(
                            in_pointer_range(int(p["expected"], 16)),
                            f"{name}:{checkpoint['name']} probe {p['address']} is a pointer oracle",
                        )

        # Suite-level liveness: the hub scenario must show a real progress
        # CHANGE (title chapterIndex 0x00 -> world-map 0x10) that a frozen
        # screen could never produce.
        _, hub = self._load("debugtools-hub-modern-release.json")

        def chapter_index(checkpoint):
            for p in checkpoint["probes"]:
                if p["address"] == "0x020210ae":
                    return p["expected"]
            self.fail(f"hub checkpoint {checkpoint['name']!r} missing chapterIndex probe")

        values = {chapter_index(cp) for cp in hub["checkpoints"]}
        self.assertEqual(
            values, {"0x00", "0x10"},
            "hub release scenario must exhibit the title -> world-map chapterIndex change",
        )


class DebugToolsCh4PrepLaunchScenarioSchemaTests(unittest.TestCase):
    """Validates the issue #11 closure Ch4-Prep-launch playtest scenarios
    (the second, independent "Fast Boot: Ch4 Prep" launcher's own
    pending-request/boot-commit lifecycle, live-executed against a real
    debug build, plus its release compiled-out mirror) against
    gba_playtest's own schema parser, mirroring
    DebugToolsScenarioSchemaTests'/DebugToolsMapPrepScenarioSchemaTests'
    pattern for the earlier Chapter 2 launcher scenarios."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPO_ROOT / "tools" / "gba-playtest"))
        global gba_playtest
        import gba_playtest  # noqa: F401

    def _load(self, name):
        import json
        path = REPO_ROOT / "tools" / "gba-playtest" / "scenarios" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        return gba_playtest.parse_scenario_data(data), data

    def test_debug_scenario_is_schema_valid_and_has_expected_checkpoints(self):
        scenario, data = self._load("debugtools-ch4-prep-launch-modern-debug.json")
        self.assertEqual(scenario.name, "debugtools-ch4-prep-launch-modern-debug")
        by_name = {c["name"]: c for c in data["checkpoints"]}
        for expected_name in (
            "hub-closed-before-hotkey",
            "hub-opened-after-pulse",
            "ch4-prep-request-armed",
            "gamecontrol-committed-chapter4-boot",
        ):
            self.assertIn(expected_name, by_name, f"missing checkpoint {expected_name!r}")

    def test_debug_scenario_reuses_the_hub_scenarios_frame_prefix(self):
        """Must build on top of the already-verified title-progression
        intro sequence (debugtools-hub-modern-debug.json's own prefix
        before its first hotkey pulse), not a fresh/independent boot
        script."""
        _, ch4_data = self._load("debugtools-ch4-prep-launch-modern-debug.json")
        _, hub_data = self._load("debugtools-hub-modern-debug.json")

        hub_prefix = [f for f in hub_data["frames"] if f["start"] < 600]
        ch4_prefix = [f for f in ch4_data["frames"] if f["start"] < 600]
        self.assertEqual(
            ch4_prefix, hub_prefix,
            "the Ch4-Prep-launch scenario's pre-hotkey frame prefix must exactly match "
            "the title-hub scenario's own (same proven intro-advance sequence)",
        )

    def test_debug_scenario_navigates_past_weather_fog_to_reach_ch4_prep(self):
        """The hub menu order is Chapter2(0)/Weather(1)/Fog(2)/Ch4Prep(3)/
        five tools(4-8) -- reaching "Fast Boot: Ch4 Prep" from a freshly
        opened hub therefore requires exactly three DOWN presses before
        the confirming A, proving this scenario's own input script
        actually targets the fourth hub row, not accidentally Weather/Fog
        or the Chapter 2 launcher itself."""
        _, data = self._load("debugtools-ch4-prep-launch-modern-debug.json")
        post_hotkey = [f for f in data["frames"] if f["start"] >= 600]
        key_sequence = [tuple(f["keys"]) for f in sorted(post_hotkey, key=lambda f: f["start"])]
        self.assertEqual(
            key_sequence,
            [
                ("SELECT", "R"),
                ("DOWN",),
                ("DOWN",),
                ("DOWN",),
                ("A",),
                ("A",),
            ],
            f"expected exactly one hotkey pulse, three DOWN presses, then two A presses, found: {key_sequence}",
        )

    def test_debug_scenario_probe_addresses_match_documented_struct_offsets(self):
        """gDebugToolsProbe's pendingCh4PrepLaunchRequest/ch4PrepLauncherArmed/
        ch4PrepLaunchRequestConsumedCount fields sit at offsets 0x30/0x34/0x38
        from the struct base (include/expansion_debugtools.h) -- confirms
        this scenario's own hardcoded addresses were derived from the same
        base nm-verified elsewhere (docs/debugtools.md), not independently
        (and possibly incorrectly) guessed.
        """
        _, data = self._load("debugtools-ch4-prep-launch-modern-debug.json")
        by_name = {c["name"]: c for c in data["checkpoints"]}
        base = int(by_name["hub-closed-before-hotkey"]["probes"][0]["address"], 16)

        armed_checkpoint = by_name["gamecontrol-committed-chapter4-boot"]
        addresses = {p["address"] for p in armed_checkpoint["probes"]}
        self.assertIn("0x%08x" % (base + 0x34), addresses, "ch4PrepLauncherArmed must be at offset 0x34")

        armed_probe_checkpoint = by_name["ch4-prep-request-armed"]
        pending_addresses = {p["address"]: p["expected"] for p in armed_probe_checkpoint["probes"]}
        self.assertEqual(
            pending_addresses.get("0x%08x" % (base + 0x30)), "0x44424c32",
            "pendingCh4PrepLaunchRequest (offset 0x30) must read the DEBUGTOOLS_LAUNCH_REQUEST_MAGIC "
            "('DBL2') while armed",
        )

    def test_release_scenario_reuses_debug_scenarios_frames_and_stays_all_zero(self):
        """The release mirror must replay the identical frame-for-frame
        input script (not a hand-authored approximation) and assert every
        probe stays 0x00000000 throughout -- proving the Ch4 Prep launcher
        is compiled out entirely in a release build, exactly like the
        Chapter 2 launcher's own release mirror."""
        _, debug_data = self._load("debugtools-ch4-prep-launch-modern-debug.json")
        _, release_data = self._load("debugtools-ch4-prep-launch-modern-release.json")

        self.assertEqual(release_data["frames"], debug_data["frames"])

        for checkpoint in release_data["checkpoints"]:
            for probe in checkpoint["probes"]:
                self.assertEqual(
                    probe["expected"], "0x00000000",
                    f"release checkpoint {checkpoint['name']!r} probe {probe['address']} "
                    "must expect 0x00000000",
                )


if __name__ == "__main__":
    unittest.main()
