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
        self.assertNotIn("CopyString", special)
        self.assertNotIn("CopyString", tact)

        cg = self._read("src/cgtext.c")
        copy_name = _function_body(cg, "CgText_CopyName")
        self.assertNotIn("iter[1]", copy_name)
        self.assertNotIn("+= 2", copy_name)
        self.assertIn("CG_TEXT_NAME_BUFFER_CAPACITY", cg)

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
