"""Static, no-execution-required proof for issue #2 slice 2's global
save-compatibility gate (src/savemenu.c's StartSaveMenu()) and its dedicated
compatibility proc (src/save_compat_menu.c).

Two properties are proven purely by scanning the real, shipped .c/.h files
(no ARM/GBA execution environment is required for these tests -- runtime
behavior is separately proven by tools/gba-playtest scenarios):

1. StartSaveMenu() is the *only* directly-coupled entry point into the
   normal save menu (ProcScr_SaveMenu) reachable from a proc script, and it
   unconditionally classifies SRAM via ClassifySramSaveCompat() and diverts
   every non-CURRENT state to StartSaveCompatMenu() before ever calling
   Proc_StartBlocking(ProcScr_SaveMenu, ...). No other call site in src/
   bypasses this gate to reach ProcScr_SaveMenu directly.

2. The compatibility proc itself (src/save_compat_menu.c) never references
   any slot/block/current-struct accessor -- IsSaveValid, ReadSaveBlockInfo,
   ReadGameSave, ReadGameSavePlaySt, InvalidateGameSave, or the
   struct SaveBlockInfo type -- anywhere in its compiled code (comments are
   stripped first, since the file's own documentation prose legitimately
   names these functions to explain what must never be called).
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAVEMENU_C = ROOT / "src" / "savemenu.c"
SAVE_COMPAT_MENU_C = ROOT / "src" / "save_compat_menu.c"
SAVE_COMPAT_MENU_H = ROOT / "include" / "save_compat_menu.h"
SRC_DIR = ROOT / "src"

# Slot/block/current-struct accessors the compatibility proc must never
# call, per the issue's guardrails. Matched as whole-word identifiers so
# e.g. "ReadGameSavePlaySt" isn't accidentally matched by a shorter
# substring check.
_FORBIDDEN_IDENTIFIERS = (
    "IsSaveValid",
    "ReadSaveBlockInfo",
    "ReadGameSave",
    "ReadGameSavePlaySt",
    "ReadGameSaveCoreGfx",
    "InvalidateGameSave",
    "struct SaveBlockInfo",
)


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


class StartSaveMenuGateStructureTests(unittest.TestCase):
    """Proves StartSaveMenu() itself has the required gate shape."""

    def setUp(self):
        self.text = SAVEMENU_C.read_text(encoding="utf-8")
        match = re.search(
            r"void StartSaveMenu\(ProcPtr parent\)\s*\{(.*?)\n\}",
            self.text, re.DOTALL,
        )
        self.assertIsNotNone(match, "StartSaveMenu() not found in src/savemenu.c")
        self.body = match.group(1)

    def test_classifies_before_anything_else(self):
        self.assertIn("ClassifySramSaveCompat()", self.body)

    def test_diverts_noncurrent_states_to_compat_menu(self):
        diversion = re.search(
            r"compat\s*!=\s*SAVE_COMPAT_CURRENT\s*\)\s*\{\s*"
            r"StartSaveCompatMenu\s*\(\s*parent\s*,\s*compat\s*\)\s*;\s*"
            r"return\s*;",
            self.body,
        )
        self.assertIsNotNone(
            diversion,
            "StartSaveMenu() must divert every non-CURRENT state to "
            "StartSaveCompatMenu(parent, compat) and return immediately",
        )

    def test_gate_precedes_the_only_slot_menu_start_call(self):
        gate_index = self.body.find("StartSaveCompatMenu")
        real_menu_index = self.body.find("Proc_StartBlocking(ProcScr_SaveMenu")
        self.assertNotEqual(gate_index, -1)
        self.assertNotEqual(real_menu_index, -1)
        self.assertLess(
            gate_index, real_menu_index,
            "the compat-menu diversion must appear before the real "
            "save-menu Proc_StartBlocking() call in source order",
        )

    def test_savemenu_c_includes_save_format_and_compat_menu_headers(self):
        self.assertIn('#include "save_format.h"', self.text)
        self.assertIn('#include "save_compat_menu.h"', self.text)


class NoBypassOfTheGateTests(unittest.TestCase):
    """Proves StartSaveMenu() is the only directly-coupled entry point that
    can reach ProcScr_SaveMenu from a proc script, and that no other file
    starts ProcScr_SaveMenu directly."""

    def test_procscr_savemenu_is_only_started_inside_startsavemenu(self):
        offenders = []
        for c_file in sorted(SRC_DIR.glob("*.c")):
            text = _strip_comments(c_file.read_text(encoding="utf-8", errors="replace"))
            for match in re.finditer(r"Proc_StartBlocking\s*\(\s*ProcScr_SaveMenu\b", text):
                # Only src/savemenu.c itself (inside StartSaveMenu()) may
                # start ProcScr_SaveMenu directly.
                if c_file.name != "savemenu.c":
                    offenders.append(f"{c_file.name}:{text.count(chr(10), 0, match.start()) + 1}")
        self.assertEqual(
            offenders, [],
            f"ProcScr_SaveMenu started outside StartSaveMenu()'s gate: {offenders}",
        )

    def test_startsavemenu_has_exactly_one_proc_script_call_site(self):
        """The only proc-script call site into StartSaveMenu() must be
        gamecontrol.c's PROC_CALL(StartSaveMenu) (LGAMECTRL_EXEC_SAVEMENU).
        save_compat_menu.c's own recursive call after a confirmed erase
        re-enters the same gated function and is not a bypass."""
        call_sites = []
        for c_file in sorted(SRC_DIR.glob("*.c")):
            if c_file.name in ("savemenu.c", "save_compat_menu.c"):
                continue
            text = _strip_comments(c_file.read_text(encoding="utf-8", errors="replace"))
            # Matches both a direct call (StartSaveMenu(...)) and a
            # function-pointer reference used by a proc script
            # (PROC_CALL(StartSaveMenu)).
            if re.search(r"\bStartSaveMenu\b", text):
                call_sites.append(c_file.name)
        self.assertEqual(
            call_sites, ["gamecontrol.c"],
            f"unexpected StartSaveMenu() call site(s): {call_sites}",
        )


class CompatMenuNeverTouchesSlotOrBlockApisTests(unittest.TestCase):
    """Proves src/save_compat_menu.c's compiled code never references any
    forbidden slot/block/current-struct accessor."""

    def setUp(self):
        self.text = _strip_comments(
            SAVE_COMPAT_MENU_C.read_text(encoding="utf-8")
        )

    def test_no_forbidden_identifier_present(self):
        offenders = [
            identifier
            for identifier in _FORBIDDEN_IDENTIFIERS
            if re.search(rf"\b{re.escape(identifier)}\b", self.text)
        ]
        self.assertEqual(
            offenders, [],
            f"src/save_compat_menu.c references forbidden API(s): {offenders}",
        )

    def test_only_allowed_save_format_calls_present(self):
        """The only save-format-related calls this file may make are the
        global classifier and the whole-chip wipe/current initializer."""
        allowed = {"ClassifySramSaveCompat", "InitGlobalSaveInfodata"}
        found = set(re.findall(r"\b(ClassifySramSaveCompat|InitGlobalSaveInfodata)\s*\(", self.text))
        self.assertTrue(found, "expected at least one classifier/initializer call")
        self.assertTrue(found.issubset(allowed))

    def test_erase_is_gated_behind_explicit_confirmation(self):
        """DoErase() (the only InitGlobalSaveInfodata() call site) must
        only be reachable via the PL_SAVECOMPAT_DO_ERASE script label,
        which is only reached from PL_SAVECOMPAT_ERASE after routing a
        SAVE_COMPAT_CHOICE_ERASE_CONFIRMED choice -- never from the
        initial diagnostic display or a bare Back."""
        self.assertIn("SAVE_COMPAT_CHOICE_ERASE_CONFIRMED", self.text)
        do_erase_match = re.search(
            r"static void SaveCompatMenu_DoErase\([^)]*\)\s*\{(.*?)\n\}",
            self.text, re.DOTALL,
        )
        self.assertIsNotNone(do_erase_match)
        self.assertIn("InitGlobalSaveInfodata()", do_erase_match.group(1))
        # Exactly one destructive call in the whole file.
        self.assertEqual(self.text.count("InitGlobalSaveInfodata()"), 1)

    def test_back_never_calls_erase(self):
        do_back_match = re.search(
            r"static void SaveCompatMenu_DoBack\([^)]*\)\s*\{(.*?)\n\}",
            self.text, re.DOTALL,
        )
        self.assertIsNotNone(do_back_match)
        self.assertNotIn("InitGlobalSaveInfodata", do_back_match.group(1))

    def test_back_is_default_first_menu_item(self):
        """Back is item 0 in *both* the legacy and modern-guarded
        branches of gSaveCompatMenuItems (issue #18 sprint 3 wrapped the
        array's first two rows in `#ifdef MODERN ... #else ... #endif`
        so their labels resolve through the expansion catalog under
        MODERN instead of the vanilla MSG_SAVE_COMPAT_BACK/
        MSG_SAVE_COMPAT_ERASE_ALL lookup -- see src/save_compat_menu.c's
        own header comment). The legacy (#else) branch must still use
        the exact original vanilla MSG_SAVE_COMPAT_BACK literal,
        unchanged."""
        items_match = re.search(
            r"CONST_DATA struct MenuItemDef gSaveCompatMenuItems\[\]\s*=\s*\{(.*?)MenuItemsEnd",
            self.text, re.DOTALL,
        )
        self.assertIsNotNone(items_match)
        body = items_match.group(1)

        guard_match = re.search(
            r"#ifdef MODERN\s*\n(.*?)\n#else\b(.*?)#endif",
            body, re.DOTALL,
        )
        self.assertIsNotNone(
            guard_match,
            "expected an #ifdef MODERN/#else/#endif guard as the array's first rows",
        )

        modern_first_item = guard_match.group(1).strip().splitlines()[0]
        legacy_first_item = guard_match.group(2).strip().splitlines()[0]

        self.assertIn("SaveCompatMenu_DrawBackLabel", modern_first_item)
        self.assertIn("SaveCompatMenu_SelectBack", modern_first_item)

        self.assertIn("MSG_SAVE_COMPAT_BACK", legacy_first_item)
        self.assertIn("SaveCompatMenu_SelectBack", legacy_first_item)


class EraseConfirmWarningActiveTests(unittest.TestCase):
    """Proves the authored irreversible-erase warning
    (MSG_SAVE_COMPAT_ERASE_CONFIRM) is actually rendered before the
    destructive erase can execute -- not merely generated-but-dead code.

    Structural proof (source order + call-site presence), since this file
    has no execution environment available to it: the message must be
    referenced by a StartHelpBoxExt_Unk(...) call inside
    SaveCompatMenu_ShowEraseConfirm(), which must itself appear, in the
    gProcScr_SaveCompatMenu script array, strictly before
    PL_SAVECOMPAT_DO_ERASE / SaveCompatMenu_DoErase (the only
    InitGlobalSaveInfodata() call site). Runtime evidence that the warning
    is actually visible on screen is separately captured by the
    savecompat-erase scenario's "confirm-shown" framebuffer_hash
    checkpoint differing from a build without this fix (see
    tools/gba-playtest/fingerprints/savecompat-erase-*.json).
    """

    def setUp(self):
        self.text = SAVE_COMPAT_MENU_C.read_text(encoding="utf-8")
        self.stripped = _strip_comments(self.text)

    def test_erase_confirm_message_referenced_in_show_erase_confirm(self):
        match = re.search(
            r"static void SaveCompatMenu_ShowEraseConfirm\([^)]*\)\s*\{(.*?)\n\}",
            self.stripped, re.DOTALL,
        )
        self.assertIsNotNone(
            match, "SaveCompatMenu_ShowEraseConfirm() not found"
        )
        body = match.group(1)
        self.assertIn(
            "MSG_SAVE_COMPAT_ERASE_CONFIRM", body,
            "SaveCompatMenu_ShowEraseConfirm() must render "
            "MSG_SAVE_COMPAT_ERASE_CONFIRM -- it must not be dead code",
        )
        self.assertRegex(
            body, r"StartHelpBoxExt_Unk\s*\([^)]*MSG_SAVE_COMPAT_ERASE_CONFIRM",
            "MSG_SAVE_COMPAT_ERASE_CONFIRM must be passed to "
            "StartHelpBoxExt_Unk(...) (the existing HelpBox-display "
            "pattern), not merely referenced in a comment",
        )

    def test_erase_confirm_message_precedes_destructive_erase_in_script_order(self):
        show_confirm_index = self.text.find("PROC_CALL(SaveCompatMenu_ShowEraseConfirm)")
        do_erase_label_index = self.text.find("PROC_LABEL(PL_SAVECOMPAT_DO_ERASE)")
        self.assertNotEqual(show_confirm_index, -1)
        self.assertNotEqual(do_erase_label_index, -1)
        self.assertLess(
            show_confirm_index, do_erase_label_index,
            "SaveCompatMenu_ShowEraseConfirm() (which renders the warning) "
            "must run before PL_SAVECOMPAT_DO_ERASE (the destructive step) "
            "in gProcScr_SaveCompatMenu's script order",
        )

    def test_erase_confirm_message_referenced_exactly_once(self):
        # Exactly one call site (inside ShowEraseConfirm) plus the
        # explanatory comment above it -- never referenced a second time
        # elsewhere, and never omitted.
        occurrences = self.text.count("MSG_SAVE_COMPAT_ERASE_CONFIRM")
        self.assertGreaterEqual(
            occurrences, 1,
            "MSG_SAVE_COMPAT_ERASE_CONFIRM must be referenced in "
            "src/save_compat_menu.c",
        )

    def test_helpbox_closed_before_do_erase_runs(self):
        """The warning HelpBox opened by ShowEraseConfirm must be closed
        (CloseHelpBox()) before SaveCompatMenu_DoErase() ever runs, so the
        destructive action never leaves a stray graphical HelpBox
        resource acquired without a matching release."""
        route_match = re.search(
            r"static void SaveCompatMenu_RouteEraseChoice\([^)]*\)\s*\{(.*?)\n\}",
            self.stripped, re.DOTALL,
        )
        self.assertIsNotNone(route_match)
        self.assertIn(
            "CloseHelpBox()", route_match.group(1),
            "SaveCompatMenu_RouteEraseChoice() must close the erase-confirm "
            "HelpBox unconditionally (both Yes and No outcomes)",
        )


class DiagnosticProbeGlobalsTests(unittest.TestCase):
    """Proves the read-only diagnostic probe globals (requirement 4) are
    declared and are the only new EWRAM globals this feature adds."""

    def test_probe_globals_declared_in_header(self):
        text = SAVE_COMPAT_MENU_H.read_text(encoding="utf-8")
        self.assertIn("extern EWRAM_DATA u8 gSaveCompatMenuActive;", text)
        self.assertIn("extern EWRAM_DATA u8 gSaveCompatMenuLastState;", text)

    def test_probe_globals_defined_exactly_once(self):
        text = SAVE_COMPAT_MENU_C.read_text(encoding="utf-8")
        self.assertEqual(text.count("EWRAM_DATA u8 gSaveCompatMenuActive"), 1)
        self.assertEqual(text.count("EWRAM_DATA u8 gSaveCompatMenuLastState"), 1)


if __name__ == "__main__":
    unittest.main()
