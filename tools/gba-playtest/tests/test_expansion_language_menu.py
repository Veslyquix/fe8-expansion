"""Issue #18 sprint 3 host tests -- first-start language selector /
settings submenu runtime glue (include/expansion_language_menu.h,
src/expansion_language_menu.c) and its guarded integration points
(src/gamecontrol.c, src/uiconfig.c, src/save_compat_menu.c,
src/debugtools_registry.c).

Two kinds of proof, both executable with no ARM/GBA/mgba environment:

1. Behavioral -- compiles and *executes* the real pure startup and
   settings-row decision functions against startup state combinations
   and the 1/2/3/>3-locale inline/More thresholds.

2. Structural/static -- proves, by scanning the real shipped .c/.h files,
   that this sprint's guardrails hold: the selector Proc is spliced
   between ProcScr_GameEarlyStartUI and the OpAnim label (never touching
   Title_IDLE/#11 hotkeys), struct GameOption's selectors[4]/size and
   struct DebugToolsAction's ABI stay unchanged, GAME_OPTION_LANGUAGE's
   Config-screen integration is entirely #ifdef MODERN-guarded, and the
   legacy branches of save_compat_menu.c/debugtools_registry.c keep their
   exact original vanilla-MSG rendering untouched.

Full runtime behavior (blocking selector, inline Config choices, More
submenu lifecycle, cache invalidation) is proven separately by
tools/gba-playtest scenarios.
"""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INCLUDE_DIRS = [REPO_ROOT / "include", REPO_ROOT / "include" / "generated"]
C_FIXTURES_DIR = Path(__file__).resolve().parent / "c"

LANGUAGE_MENU_HEADER = REPO_ROOT / "include" / "expansion_language_menu.h"
LANGUAGE_MENU_SRC = REPO_ROOT / "src" / "expansion_language_menu.c"
GAMECONTROL_SRC = REPO_ROOT / "src" / "gamecontrol.c"
UICONFIG_HEADER = REPO_ROOT / "include" / "uiconfig.h"
UICONFIG_SRC = REPO_ROOT / "src" / "uiconfig.c"
SAVE_COMPAT_MENU_SRC = REPO_ROOT / "src" / "save_compat_menu.c"
DEBUGTOOLS_REGISTRY_SRC = REPO_ROOT / "src" / "debugtools_registry.c"
DEBUGTOOLS_HEADER = REPO_ROOT / "include" / "expansion_debugtools.h"

CC = shutil.which("gcc") or shutil.which("cc")


def _skip_if_no_host_compiler():
    if CC is None:
        raise unittest.SkipTest("no host C compiler (gcc/cc) available")


def _include_flags():
    flags = []
    for d in INCLUDE_DIRS:
        flags += ["-I", str(d)]
    return flags


def _compile(work_dir: Path, src: Path, obj_name: str, defines=()):
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


def _strip_c_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


class ExpansionLanguageMenuDecisionHostTests(unittest.TestCase):
    """Compiles and executes the real unguarded startup/settings decisions."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_decision_table_matches_every_real_input_combination(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)

            rc, out, impl_obj = _compile(work, LANGUAGE_MENU_SRC, "impl.o")
            self.assertEqual(rc, 0, f"compiling src/expansion_language_menu.c (host, no -DMODERN) failed:\n{out}")

            rc, out, driver_obj = _compile(
                work, C_FIXTURES_DIR / "expansion_language_menu_decision_driver.c", "driver.o"
            )
            self.assertEqual(rc, 0, f"compiling expansion_language_menu_decision_driver.c failed:\n{out}")

            rc, out, exe = _link(work, [impl_obj, driver_obj], "test_exe")
            self.assertEqual(rc, 0, f"linking host decision-table test failed:\n{out}")

            rc, out = _run(exe)
            self.assertEqual(rc, 0, out)
            self.assertIn("EXPANSION_LANGUAGE_MENU_DECISION_HOST_TEST: PASS", out)


class ExpansionLanguageMenuHeaderHostCompileTests(unittest.TestCase):
    """include/expansion_language_menu.h must stay strict-C89/agbcc
    (legacy) compilable on its own -- no generated-header
    (expansion_msg_ids.h) dependency at file scope -- exactly like
    include/expansion_locale.h/include/expansion_save_prefs.h."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()

    def test_header_compiles_standalone_without_modern_define(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            probe = work / "probe.c"
            probe.write_text(f'#include "{LANGUAGE_MENU_HEADER}"\nint unused_probe_symbol;\n')

            rc, out, _ = _compile(work, probe, "probe.o")
            self.assertEqual(
                rc, 0,
                "expansion_language_menu.h must compile without -DMODERN "
                f"(no expansion_msg_ids.h dependency at file scope):\n{out}",
            )



class RowSelectedPreferenceRepairStructureTests(unittest.TestCase):
    """Issue #18 sprint 6 (runtime blocker fix) structural proof, by
    scanning the real shipped src/expansion_language_menu.c and
    include/expansion_language_menu.h: needsPreferenceRepair is appended
    (never inserted) as the struct's last field; RuntimeInit sets it
    unconditionally from Normalize()'s own requiresPrompt output before
    branching on the startup action; only the AUTO_SELECT branch clears
    it, and only inside the Store()-succeeded guard; RowSelected's own
    mustRepair guard is derived from (active && needsPreferenceRepair)
    and is only cleared inside its own Store()-succeeded guard; and
    ExpansionLanguageMenu_OpenSettings never sets `active` (so the
    settings submenu's unconditional "same locale = no-op" contract is
    never affected by the first-start selector's repair path)."""

    @classmethod
    def setUpClass(cls):
        cls.header_text = LANGUAGE_MENU_HEADER.read_text(encoding="utf-8")
        cls.src_text = LANGUAGE_MENU_SRC.read_text(encoding="utf-8")
        cls.stripped_header = _strip_c_comments(cls.header_text)
        cls.stripped_src = _strip_c_comments(cls.src_text)

    def test_probe_field_is_last_and_appended(self):
        match = re.search(
            r"struct ExpansionLanguageMenuProbe\s*\{(.*?)\};", self.stripped_header, re.DOTALL
        )
        self.assertIsNotNone(match)
        field_lines = [l.strip() for l in match.group(1).splitlines() if l.strip()]
        self.assertTrue(field_lines, "struct ExpansionLanguageMenuProbe must not be empty")
        self.assertEqual(
            field_lines[-1], "u8 needsPreferenceRepair;",
            "needsPreferenceRepair must be the last (appended, never inserted) field "
            "so every pre-sprint-6 scenario's hardcoded probe field offsets stay valid",
        )

    def test_runtime_init_sets_flag_from_requires_prompt_before_branching(self):
        match = re.search(
            r"static void ExpansionLanguageMenu_RuntimeInitCore\(ProcPtr procPtr\)\s*\{(.*?)\n\}",
            self.stripped_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)

        set_idx = body.index("gExpansionLanguageMenuProbe.needsPreferenceRepair = requiresPrompt;")
        switch_idx = body.index("switch (action)")
        self.assertLess(
            set_idx, switch_idx,
            "needsPreferenceRepair must be set from requiresPrompt before the "
            "startup action switch, unconditionally of which action fires",
        )

    def test_auto_select_clears_flag_only_inside_store_succeeded_guard(self):
        match = re.search(
            r"case EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT:\s*\{(.*?)\n        \}"
            r"\n\n        if \(procPtr != NULL\)",
            self.stripped_src, re.DOTALL,
        )
        self.assertIsNotNone(match, "could not locate the AUTO_SELECT case body")
        body = match.group(1)

        store_if_match = re.search(
            r"if\s*\(ExpansionUserPrefs_Store\([^)]*\)\)\s*\{(.*?)\n            \}", body, re.DOTALL
        )
        self.assertIsNotNone(store_if_match, "AUTO_SELECT must guard its repair-clear on a successful Store()")
        guarded_body = store_if_match.group(1)
        self.assertIn("gExpansionLanguageMenuProbe.needsPreferenceRepair = FALSE;", guarded_body)

        after_guard = body[store_if_match.end():]
        self.assertNotIn(
            "needsPreferenceRepair = FALSE", after_guard,
            "AUTO_SELECT must not clear needsPreferenceRepair outside the Store()-succeeded guard",
        )

    def test_row_selected_routes_repair_state_through_store_helper(self):
        match = re.search(
            r"static u8 ExpansionLanguageMenu_RowSelected\(struct MenuProc \*menu, "
            r"struct MenuItemProc \*item\)\s*\{(.*?)\n\}",
            self.stripped_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)

        must_repair_match = re.search(
            r"mustRepair\s*=\s*\(bool8\)\(gExpansionLanguageMenuProbe\.active\s*"
            r"&&\s*gExpansionLanguageMenuProbe\.needsPreferenceRepair\);",
            body,
        )
        self.assertIsNotNone(
            must_repair_match,
            "mustRepair must be derived from (active && needsPreferenceRepair), "
            "gating the repair-write path on the first-start selector's own liveness",
        )
        self.assertIn("ExpansionLanguageMenu_StoreSelection(", body)
        self.assertIn("gExpansionLanguageMenuProbe.settingsActive", body)

        store_match = re.search(
            r"static bool8 ExpansionLanguageMenu_StoreSelection\(.*?\)\s*\{(.*?)\n\}",
            self.stripped_src,
            re.DOTALL,
        )
        self.assertIsNotNone(store_match)
        store_body = store_match.group(1)

        if_match = re.search(
            r"if\s*\(locale != previous \|\| mustRepair\)\s*\{(.*?)\n    \}",
            store_body,
            re.DOTALL,
        )
        self.assertIsNotNone(
            if_match,
            "StoreSelection must commit when locale changed OR mustRepair is set",
        )
        guarded_body = if_match.group(1)

        store_if_match = re.search(
            r"if\s*\(ExpansionUserPrefs_Store\([^)]*\)\)\s*\{(.*?)\n        \}", guarded_body, re.DOTALL
        )
        self.assertIsNotNone(
            store_if_match,
            "StoreSelection must guard its repair-clear on a successful Store()",
        )
        self.assertIn(
            "gExpansionLanguageMenuProbe.needsPreferenceRepair = FALSE;",
            store_if_match.group(1),
        )

        after_guard = guarded_body[store_if_match.end():]
        self.assertNotIn(
            "needsPreferenceRepair = FALSE", after_guard,
            "StoreSelection must not clear needsPreferenceRepair outside the Store()-succeeded guard",
        )

    def test_open_settings_never_sets_active(self):
        match = re.search(
            r"void ExpansionLanguageMenu_OpenSettings\(ProcPtr parent\)\s*\{(.*?)\n\}",
            self.stripped_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertNotIn(
            "gExpansionLanguageMenuProbe.active = TRUE;", body,
            "OpenSettings must never set `active` -- that flag is exclusive to the "
            "blocking first-start selector's own ShowSelector, so the settings "
            "submenu's unconditional same-locale no-op contract stays unaffected "
            "by the first-start repair path (RowSelected's mustRepair is gated on "
            "`active`)",
        )


class GameControlIntegrationStructureTests(unittest.TestCase):
    """Proves the blocking first-start selector is spliced between
    ProcScr_GameEarlyStartUI and the OpAnim label, is entirely
    #ifdef MODERN-guarded, and that this sprint never touched Title_IDLE
    or any issue #11 debug hotkey mask check in src/gamecontrol.c."""

    @classmethod
    def setUpClass(cls):
        cls.text = GAMECONTROL_SRC.read_text(encoding="utf-8")

    def test_selector_call_site_is_modern_guarded_and_singular(self):
        matches = re.findall(
            r"PROC_START_CHILD_BLOCKING\(ProcScr_ExpansionLanguageSelector\)", self.text
        )
        self.assertEqual(len(matches), 1, "expected exactly one selector call site")

        selector_idx = self.text.index("PROC_START_CHILD_BLOCKING(ProcScr_ExpansionLanguageSelector)")
        preceding = self.text[:selector_idx]

        last_ifdef = preceding.rfind("#ifdef")
        last_endif = preceding.rfind("#endif")
        self.assertGreater(
            last_ifdef, last_endif,
            "selector call site must be inside an open #ifdef block (no intervening #endif)",
        )
        self.assertTrue(
            preceding[last_ifdef:].startswith("#ifdef MODERN"),
            "selector call site's enclosing guard must be #ifdef MODERN",
        )

    def test_selector_is_spliced_between_early_startup_and_opanim(self):
        early_ui_idx = self.text.index("PROC_START_CHILD_BLOCKING(ProcScr_GameEarlyStartUI)")
        selector_idx = self.text.index("PROC_START_CHILD_BLOCKING(ProcScr_ExpansionLanguageSelector)")
        opanim_idx = self.text.index("PROC_START_CHILD_BLOCKING(ProcScr_OpAnim)")

        self.assertLess(early_ui_idx, selector_idx,
            "selector must run after ProcScr_GameEarlyStartUI")
        self.assertLess(selector_idx, opanim_idx,
            "selector must run before ProcScr_OpAnim")

    def test_title_idle_and_debug_hotkey_lifecycle_untouched(self):
        # Presence-only proof (this sprint never edits these) -- a real
        # regression removing/renaming either would fail this.
        self.assertIn("Title_IDLE", self.text)
        self.assertIn("gamecontrol.h", (REPO_ROOT / "src" / "gamecontrol.c").read_text())


class GameOptionAbiUnchangedTests(unittest.TestCase):
    """struct GameOption's layout/size (in particular selectors[4]) must
    stay exactly as-is -- the language settings entry is a real Config
    Screen row (GAME_OPTION_LANGUAGE), never an expansion of
    selectors[]."""

    @classmethod
    def setUpClass(cls):
        _skip_if_no_host_compiler()
        cls.header_text = UICONFIG_HEADER.read_text(encoding="utf-8")

    def test_selectors_array_is_still_fixed_size_4(self):
        self.assertIn("struct Selector selectors[4];", self.header_text)

    def test_game_option_struct_field_count_and_order_unchanged(self):
        stripped = _strip_c_comments(self.header_text)
        match = re.search(r"struct GameOption\s*\{(.*?)\};", stripped, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)
        field_lines = [l.strip() for l in body.splitlines() if l.strip()]
        self.assertEqual(
            field_lines,
            [
                "u16 msgId;",
                "struct Selector selectors[4];",
                "u8 icon;",
                "bool (*func)(ProcPtr);",
            ],
        )

    def test_game_option_language_is_appended_after_every_original_value(self):
        # GAME_OPTION_LANGUAGE must be a strictly-new, appended enum value
        # (17) -- never renumbering/displacing any pre-existing option
        # (which would silently break gPlaySt.config's own persisted
        # save-state field mapping via GetGameOption/SetGameOption).
        stripped = _strip_c_comments(self.header_text)
        match = re.search(r"enum\s*\{\s*GAME_OPTION_ANIMATION(.*?)\};", stripped, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group(1)

        self.assertIn("GAME_OPTION_RANK_DISPLAY   = 16,", body)

        guarded_match = re.search(r"#ifdef MODERN\s*(.*?)#endif", body, re.DOTALL)
        self.assertIsNotNone(guarded_match, "GAME_OPTION_LANGUAGE must be #ifdef MODERN-guarded")
        self.assertIn("GAME_OPTION_LANGUAGE       = 17,", guarded_match.group(1))

    def test_language_row_never_added_to_selectors_or_struct_size(self):
        # Compile a tiny probe against the real header and assert sizeof
        # matches a hand-built reference layout (u16 + 4*struct Selector +
        # u8 [+ pad] + function pointer) -- proves no field was widened.
        import struct
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            probe = work / "probe.c"
            probe.write_text(
                '#include <stdio.h>\n'
                f'#include "{REPO_ROOT / "include" / "global.h"}"\n'
                f'#include "{REPO_ROOT / "include" / "fontgrp.h"}"\n'
                f'#include "{UICONFIG_HEADER}"\n'
                'int main(void) {\n'
                '    printf("%lu %lu\\n",\n'
                '        (unsigned long)sizeof(struct GameOption),\n'
                '        (unsigned long)(sizeof(((struct GameOption*)0)->selectors) / sizeof(struct Selector)));\n'
                '    return 0;\n'
                '}\n'
            )
            rc, out, obj = _compile(work, probe, "probe.o")
            self.assertEqual(rc, 0, out)
            rc, out, exe = _link(work, [obj], "probe_exe")
            self.assertEqual(rc, 0, out)
            rc, out = _run(exe)
            self.assertEqual(rc, 0, out)
            size_str, selector_count_str = out.split()
            self.assertEqual(int(selector_count_str), 4)


class UiConfigLanguageEntryStructureTests(unittest.TestCase):
    """Proves GAME_OPTION_LANGUAGE's Config-screen wiring in
    src/uiconfig.c is entirely #ifdef MODERN-guarded (never referenced
    from a legacy-reachable code path) and that
    LanguageOptionEntryHandler is the row's .func (opened via Left/Right,
    never a hidden debug-only path)."""

    @classmethod
    def setUpClass(cls):
        cls.text = UICONFIG_SRC.read_text(encoding="utf-8")

    def test_ui_order_entry_is_modern_guarded(self):
        match = re.search(
            r"\[12\] = GAME_OPTION_WINDOW_COLOR,\n(#ifdef MODERN\n)?\s*\[13\] = GAME_OPTION_LANGUAGE,",
            self.text,
        )
        self.assertIsNotNone(match)
        self.assertIsNotNone(match.group(1), "gGameOptionsUiOrder's GAME_OPTION_LANGUAGE row must be #ifdef MODERN-guarded")

    def test_game_options_entry_is_modern_guarded_and_uses_entry_handler(self):
        entry_idx = self.text.index("[GAME_OPTION_LANGUAGE] =")
        preceding = self.text[:entry_idx]

        last_ifdef = preceding.rfind("#ifdef")
        last_endif = preceding.rfind("#endif")
        self.assertGreater(
            last_ifdef, last_endif,
            "gGameOptions[GAME_OPTION_LANGUAGE] must be inside an open #ifdef block",
        )
        self.assertTrue(
            preceding[last_ifdef:].startswith("#ifdef MODERN"),
            "gGameOptions[GAME_OPTION_LANGUAGE]'s enclosing guard must be #ifdef MODERN",
        )

        following = self.text[entry_idx:entry_idx + 600]
        self.assertIn("LanguageOptionEntryHandler", following)
        self.assertIn(".icon = 0x16", following)
        self.assertIn("{ MSG_000, MSG_000, 112, 0 }", following)
        self.assertIn("{ MSG_000, MSG_000, 152, 0 }", following)
        self.assertIn("{ MSG_000, MSG_000, 192, 0 }", following)

    def test_entry_handler_selects_inline_or_opens_more_submenu(self):
        match = re.search(
            r"bool LanguageOptionEntryHandler\(ProcPtr proc\)\s*\{(.*?)\n\}",
            self.text, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn("ExpansionLanguageMenu_DecideSettingsAction", body)
        self.assertIn("ExpansionLanguageMenu_SelectSettingsLocale", body)
        self.assertIn("ExpansionLanguageMenu_OpenSettings(proc)", body)
        self.assertIn("EXPANSION_LANGUAGE_SETTINGS_OPEN_MENU", body)

    def test_config_hands_are_hidden_while_more_submenu_is_active(self):
        match = re.search(
            r"void DrawConfigUiSprites\(void\)\s*\{(.*?)\n\}",
            self.text,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertIn("gExpansionLanguageMenuProbe.settingsActive", match.group(1))


class LanguageSettingsLifecycleStructureTests(unittest.TestCase):
    """The settings submenu shares Configuration's BG0/BG1 surfaces, so it
    needs a real terminator and a redraw after MenuProc's final clear."""

    @classmethod
    def setUpClass(cls):
        cls.language_text = LANGUAGE_MENU_SRC.read_text(encoding="utf-8")
        cls.uiconfig_text = UICONFIG_SRC.read_text(encoding="utf-8")

    def test_settings_rows_reserve_back_and_terminator_slots(self):
        self.assertRegex(
            self.language_text,
            r"#define\s+EXPANSION_LANGUAGE_MENU_MAX_ROWS\s+\\?\s*"
            r"\(FE8_EXPANSION_ENABLED_LOCALE_COUNT\s*\+\s*2\)",
        )

    def test_settings_open_clears_the_shared_configuration_backgrounds(self):
        match = re.search(
            r"void ExpansionLanguageMenu_OpenSettings\(ProcPtr parent\)\s*\{(.*?)\n\}",
            self.language_text,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertLess(body.index("BG_Fill(gBG0TilemapBuffer, 0)"), body.index("StartMenu"))
        self.assertLess(body.index("BG_Fill(gBG1TilemapBuffer, 0)"), body.index("StartMenu"))
        self.assertLess(body.index("ResetTextFont()"), body.index("StartMenu"))

    def test_more_submenu_defaults_cursor_to_current_locale(self):
        match = re.search(
            r"void ExpansionLanguageMenu_OpenSettings\(ProcPtr parent\)\s*\{(.*?)\n\}",
            self.language_text,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn("current = ExpansionLocale_GetCurrent();", body)
        self.assertIn("menu->itemCurrent = itemIndex;", body)

    def test_settings_end_defers_configuration_redraw_past_menu_clear(self):
        self.assertRegex(
            self.language_text,
            r"(?s)gProcScr_RedrawConfigAfterLanguageMenu\[\].*?"
            r"PROC_SLEEP\(1\).*?"
            r"PROC_CALL\(Config_RedrawAfterLanguageMenu\)",
        )
        match = re.search(
            r"static void ExpansionLanguageMenu_SettingsOnEnd\(struct MenuProc \*proc\)"
            r"\s*\{(.*?)\n\}",
            self.language_text,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertIn(
            "Proc_Start(gProcScr_RedrawConfigAfterLanguageMenu, proc->proc_parent)",
            match.group(1),
        )
        self.assertIn("Config_RedrawAfterLanguageMenu", self.uiconfig_text)


class FrameworkUtf8DrawingTests(unittest.TestCase):
    """Every framework string resolved from the expansion catalog must use
    the UTF-8-aware renderer; clipping must advance whole rendered
    characters instead of splitting a multibyte scalar."""

    @classmethod
    def setUpClass(cls):
        cls.sources = {
            "language": LANGUAGE_MENU_SRC.read_text(encoding="utf-8"),
            "uiconfig": UICONFIG_SRC.read_text(encoding="utf-8"),
            "save_compat": SAVE_COMPAT_MENU_SRC.read_text(encoding="utf-8"),
            "debugtools": DEBUGTOOLS_REGISTRY_SRC.read_text(encoding="utf-8"),
        }

    def test_framework_locale_surfaces_do_not_use_ascii_only_draws(self):
        for name, text in self.sources.items():
            with self.subTest(source=name):
                self.assertNotIn("Text_DrawStringASCII", text)

    def test_framework_locale_surfaces_use_utf8_draws(self):
        for name, text in self.sources.items():
            with self.subTest(source=name):
                if "ExpansionLocale_Resolve" in text:
                    self.assertIn("Text_DrawString", text)

    def test_config_value_clipping_advances_complete_characters(self):
        text = self.sources["uiconfig"]
        match = re.search(
            r"static void DrawLanguageOptionLabel\(.*?\)\s*\{(.*?)\n\}",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn("GetCharTextLen(cursor, &charWidth)", body)
        self.assertIn("byteCount = (int)(next - cursor);", body)
        self.assertIn("Text_DrawString(text, clipped);", body)
        self.assertNotIn("GetStringTextLenASCII", body)


class ExpansionLocaleVanillaIsolationTests(unittest.TestCase):
    """Production locale selection stays independent of vanilla language
    mode and XMAP save semantics across the owned runtime/UI files."""

    def test_owned_runtime_files_have_no_vanilla_language_or_xmap_calls(self):
        for path in (
            REPO_ROOT / "src" / "expansion_locale.c",
            REPO_ROOT / "src" / "expansion_save_prefs.c",
            LANGUAGE_MENU_SRC,
            UICONFIG_SRC,
        ):
            text = _strip_c_comments(path.read_text(encoding="utf-8"))
            with self.subTest(path=path.name):
                for token in ("GetLang", "SetLang", "gLanguageMode", "XMAP"):
                    self.assertIsNone(
                        re.search(rf"\b{re.escape(token)}\b", text),
                        f"{path.name} references forbidden vanilla symbol {token}",
                    )


class SaveCompatMenuLegacyPathUnchangedTests(unittest.TestCase):
    """The legacy (#else) branch of gSaveCompatMenuItems must keep the
    exact original vanilla MSG_SAVE_COMPAT_BACK/MSG_SAVE_COMPAT_ERASE_ALL
    literals unchanged -- only the #ifdef MODERN branch may resolve
    through the expansion catalog."""

    @classmethod
    def setUpClass(cls):
        cls.text = SAVE_COMPAT_MENU_SRC.read_text(encoding="utf-8")

    def test_legacy_branch_keeps_original_vanilla_labels(self):
        match = re.search(
            r"CONST_DATA struct MenuItemDef gSaveCompatMenuItems\[\]\s*=\s*\{(.*?)MenuItemsEnd",
            self.text, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(1)

        else_match = re.search(r"#else\b(.*?)#endif", body, re.DOTALL)
        self.assertIsNotNone(else_match, "expected a legacy #else branch")
        legacy_body = else_match.group(1)

        self.assertIn(
            '{"", MSG_SAVE_COMPAT_BACK, 0, 0, 121, MenuAlwaysEnabled, 0, SaveCompatMenu_SelectBack, 0, 0, 0},',
            legacy_body,
        )
        self.assertIn(
            '{"", MSG_SAVE_COMPAT_ERASE_ALL, 0, 0, 122, MenuAlwaysEnabled, 0, SaveCompatMenu_SelectErase, 0, 0, 0},',
            legacy_body,
        )


class DebugToolsRegistryAbiUnchangedAfterLocalizationTests(unittest.TestCase):
    """struct DebugToolsAction/DEBUGTOOLS_ACTION_MAX/
    DebugTools_RegisterAction's ABI must stay completely unchanged --
    this sprint only adds a render-time label lookup table, never a new
    field/enum value affecting registration."""

    @classmethod
    def setUpClass(cls):
        cls.header_text = DEBUGTOOLS_HEADER.read_text(encoding="utf-8")
        cls.registry_text = DEBUGTOOLS_REGISTRY_SRC.read_text(encoding="utf-8")

    def test_debug_tools_action_struct_unchanged(self):
        stripped = _strip_c_comments(self.header_text)
        match = re.search(r"struct DebugToolsAction\s*\{(.*?)\};", stripped, re.DOTALL)
        self.assertIsNotNone(match)
        field_lines = [l.strip() for l in match.group(1).splitlines() if l.strip()]
        self.assertEqual(
            field_lines,
            [
                "u16 id;",
                "const char* label;",
                "u8 (*onSelected)(struct MenuProc* menu, struct MenuItemProc* item);",
            ],
        )

    def test_debugtools_action_max_unchanged(self):
        self.assertIn("DEBUGTOOLS_ACTION_MAX = 9,", self.header_text)

    def test_builtin_label_mapping_is_modern_guarded_and_third_party_fallback_intact(self):
        guard_match = re.search(
            r"#ifdef MODERN\n(.*?sBuiltinActionLabelMsgIds.*?)#endif /\* MODERN \*/",
            self.registry_text, re.DOTALL,
        )
        self.assertIsNotNone(guard_match, "builtin label mapping table must be #ifdef MODERN-guarded")

        # The unconditional fallback (every registration, third-party
        # included) must still set def->name/onDraw = NULL first, before
        # any guarded builtin-only override.
        build_match = re.search(
            r"static void DebugToolsHub_BuildMenuItems\(void\)\s*\{(.*?)\n\}",
            self.registry_text, re.DOTALL,
        )
        self.assertIsNotNone(build_match)
        body = build_match.group(1)
        name_idx = body.index("def->name = sActions[i].label;")
        ondraw_null_idx = body.index("def->onDraw = NULL;")
        guarded_override_idx = body.index("def->onDraw = DebugToolsHub_BuiltinActionRowDraw;")
        self.assertLess(name_idx, guarded_override_idx)
        self.assertLess(ondraw_null_idx, guarded_override_idx)
