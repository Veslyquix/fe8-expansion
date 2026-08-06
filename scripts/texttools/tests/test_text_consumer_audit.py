"""Static closure checks for modern CJK text-stream consumers."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^[A-Za-z_][A-Za-z0-9_\s\*]*\b{re.escape(name)}"
        r"\s*\([^;{}]*?\)\s*\{",
        source,
        re.M | re.S,
    )
    if match is None:
        raise AssertionError(f"missing function {name}")

    depth = 1
    index = match.end()
    while index < len(source) and depth:
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
        index += 1
    if depth:
        raise AssertionError(f"unterminated function {name}")
    return source[match.start():index]


def _modern_branch(body: str) -> str:
    marker = "#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED"
    if marker not in body:
        return body
    branch = body.split(marker, 1)[1]
    return branch.split("#else", 1)[0]


class TextConsumerAuditTests(unittest.TestCase):
    def _read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_owned_walkers_use_shared_token_contract(self):
        expected = {
            "src/msg.c": (
                "SetMsgTerminator",
                "StringInsertSpecialPrefixByCtrl",
                "StrInsertTact",
            ),
            "src/scene.c": (
                "TalkInterpret",
                "PrintStringToTexts",
                "GetStrTalkLenUtf8",
            ),
            "src/cgtext.c": (
                "CgText_CopyName",
                "GetCgTextDimensions",
                "GetCgTextBoxDimensions",
                "DoesStringContainTact",
                "CgTextInterpreter_Loop_Main",
            ),
            "src/helpbox.c": (
                "HelpBoxTextScroll_OnLoop",
                "HelpBoxDrawOneLineExt",
                "GetBoxDialogueSize",
                "DialogBoxGetGlyphLen",
                "BoxDialogueInterpreter_Main",
            ),
        }
        for path, functions in expected.items():
            source = self._read(path)
            self.assertIn('#include "text_utf8.h"', source, path)
            for function in functions:
                with self.subTest(path=path, function=function):
                    self.assertIn(
                        "TextUtf8_Next", _function_body(source, function)
                    )

    def test_no_production_unknown_capacity_buffer_calls(self):
        calls = []
        pattern = re.compile(r"\bGetStringFromIndexInBuffer\s*\(")
        for path in (ROOT / "src").glob("*.c"):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not pattern.search(line):
                    continue
                if re.search(
                    r"\bchar\s*\*\s*GetStringFromIndexInBuffer\s*\(", line
                ):
                    continue
                calls.append(f"{path.relative_to(ROOT)}:{line_number}")
        self.assertEqual(calls, [])

    def test_modern_scratch_and_name_paths_are_not_legacy_fixed_pairs(self):
        msg = self._read("src/msg.c")
        special = _modern_branch(
            _function_body(msg, "StringInsertSpecialPrefixByCtrl")
        )
        tact = _modern_branch(_function_body(msg, "StrInsertTact"))
        self.assertIn("MSG_TRANSFORM_OUTPUT", special)
        self.assertIn("MSG_TRANSFORM_OUTPUT", tact)
        self.assertIn("MSG_TRANSFORM_OUTPUT_CAPACITY", msg)
        self.assertNotIn("MsgStreamWriter_CommitToActive", msg)
        self.assertIn("return writer.buffer;", special)
        self.assertIn("return writer.buffer;", tact)
        self.assertNotIn("CopyString", special)
        self.assertNotIn("CopyString", tact)

        cg = self._read("src/cgtext.c")
        copy_name = _function_body(cg, "CgText_CopyName")
        self.assertNotIn("iter[1]", copy_name)
        self.assertNotIn("+= 2", copy_name)
        self.assertIn("CG_TEXT_NAME_BUFFER_CAPACITY", cg)

    def test_reviewed_class_and_name_consumers_have_cjk_paths(self):
        opinfo = self._read("src/opinfo.c")
        for function in (
            "ClassIntro_Init",
            "ClassStatsDisplay_Init",
            "ClassStatsDisplay_Loop",
        ):
            body = _function_body(opinfo, function)
            self.assertIn(
                "FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED", body
            )
        self.assertIn("GetStringTextLen(str)", _function_body(
            opinfo, "ClassIntro_Init"
        ))
        self.assertIn("Text_DrawString", _function_body(
            opinfo, "ClassStatsDisplay_Loop"
        ))

        classchg = self._read("src/classchg-sel.c")
        palette = _function_body(classchg, "LoadClassReelFontPalette")
        draw = _function_body(classchg, "LoadClassNameInClassReelFont")
        self.assertIn("CLASS_CHANGE_NAME_CAPACITY", palette)
        self.assertIn("GetStringTextLen", palette)
        self.assertIn("CLASS_CHANGE_NAME_CAPACITY", draw)
        self.assertIn("Text_DrawString", draw)

        tactician = self._read("src/sio_tactician.c")
        mapping = _function_body(
            tactician, "Tactician_MapNameToConfIndices"
        )
        drawing = _function_body(tactician, "TacticianDrawCharacters")
        loop = _function_body(tactician, "Tactician_Loop")
        self.assertIn("TextUtf8_Next", mapping)
        self.assertIn("Text_DrawString", drawing)
        self.assertIn("GetStringTextLen(proc->str)", loop)

        rankings = self._read("src/bmsave-multiarena.c")
        self.assertIn("MULTIARENA_RANKING_LABEL", rankings)
        self.assertIn(
            "sizeof(name) <= MULTIARENA_TEAMNAME_SIZE + 1", rankings
        )
        self.assertIn(
            "GetLocalizedInitialMultiArenaRankingName", rankings
        )

    def test_equivalent_byte_walker_sites_match_reviewed_allowlist(self):
        pattern = re.compile(
            r"\b(?:str|str_buf|iter|it|ptr)\s*\+=\s*2\b"
            r"|gActiveFont->glyphs\[\*"
            r"|gOpinfo_1\[\*"
            r"|GetClassDisplayFontInfo\([^)]*\[[^]]+\]"
        )
        function_pattern = re.compile(
            r"^[A-Za-z_][A-Za-z0-9_\s\*]*\b"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*"
            r"\([^;{}]*\)\s*\{",
            re.M,
        )
        allowed = {
            ("src/bmmenu.c", "IsAdjacentForSupply"),
            ("src/cgtext.c", "CgText_DrawNameBox"),
            ("src/cgtext.c", "GetCgTextDimensions"),
            ("src/cgtext.c", "GetCgTextBoxDimensions"),
            ("src/classchg-sel.c", "LoadClassReelFontPalette"),
            ("src/classchg-sel.c", "LoadClassNameInClassReelFont"),
            ("src/eventinfo.c", "StartAvailableTileEvent"),
            ("src/fontgrp.c", "Text_DrawStringASCII"),
            ("src/fontgrp.c", "Text_DrawCharacterAscii"),
            ("src/fontgrp.c", "GetCharTextLenASCII"),
            ("src/fontgrp.c", "GetStringTextLenASCII"),
            ("src/helpbox.c", "GetBoxDialogueSize"),
            ("src/helpbox.c", "DialogBoxGetGlyphLen"),
            ("src/mapanim_infobox.c", "MapAnim_DrawBar"),
            ("src/opinfo.c", "ClassIntro_Init"),
            ("src/opinfo.c", "ClassStatsDisplay_Init"),
            ("src/opinfo.c", "ClassStatsDisplay_Loop"),
            ("src/scene.c", "TalkInterpret"),
            ("src/scene.c", "GetStrTalkLen"),
            ("src/sio_tactician.c", "Tactician_MapNameToConfIndices"),
        }
        found = set()
        for path in (ROOT / "src").rglob("*.c"):
            relative = str(path.relative_to(ROOT))
            if relative.startswith("src/data/"):
                continue
            source = path.read_text(encoding="utf-8")
            functions = [
                (match.start(), match.group(1))
                for match in function_pattern.finditer(source)
            ]
            for match in pattern.finditer(source):
                function = "<global>"
                for offset, name in functions:
                    if offset > match.start():
                        break
                    function = name
                found.add((relative, function))

        self.assertEqual(found, allowed)

    def test_unbounded_modern_abi_fails_with_actionable_marker(self):
        msg = self._read("src/msg.c")
        body = _function_body(msg, "ResolveStringIntoUnboundedBuffer")
        self.assertIn("LOCALIZED_GAME_TEXT_STATUS_LEGACY_BUFFER_UNBOUNDED", body)
        self.assertIn("LOCALIZED_GAME_TEXT_MARKER_UNBOUNDED", body)
        self.assertNotIn("ResolveCurrentToUnboundedBuffer", body)

    def test_subtitle_wrap_rewinds_to_the_saved_token_boundary(self):
        source = self._read("src/bb.c")
        body = _function_body(source, "InitSubtitleHelpText")
        self.assertIn("const char * charStart = iter", body)
        self.assertRegex(
            body,
            re.compile(
                r"#ifdef FE8_TEXT_UTF8_ENABLED\s+iter = charStart;\s+"
                r"#else\s+iter -= 2;",
                re.S,
            ),
        )


if __name__ == "__main__":
    unittest.main()
