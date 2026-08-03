"""
Issue #6 Sprint 2 host tests -- the bundled generated-data CONTENT example.

Where possible these compile and *execute* the real, unmodified project
sources (include/expansion_starter_content.h, src/expansion_starter_content.c
and the public registry in src/expansion_mechanics.c) with a native host
compiler rather than pattern-matching their logic, matching
test_expansion_mechanics.py's approach. The small driver sources live in
tools/gba-playtest/tests/c/ and are test-only (never referenced by
modern.mk/Makefile).

They also pin the two structural properties the rest of the evidence chain
depends on:

  * the disabled translation unit emits NO data at all, so a default build's
    EWRAM/BSS layout -- and therefore every committed scenario probe address
    -- is untouched by adding this feature;
  * the issue #6 implementation sources name the content item symbolically
    (ITEM_EXPANSION_CE), never as a raw numeric ID; and
  * the ORIGINAL authored display text is config-gated end to end: the
    generator writes nothing at EXPANSION_STARTER_CONTENT=0, the default
    objects contain no such string and no call into the content seam, and the
    content objects contain exactly the authored bytes and do read them
    through the production name path.
"""

import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INCLUDE_DIRS = [REPO_ROOT / "include", REPO_ROOT / "include" / "generated"]

CONTENT_SRC = REPO_ROOT / "src" / "expansion_starter_content.c"
CONTENT_HEADER = REPO_ROOT / "include" / "expansion_starter_content.h"
MECHANICS_SRC = REPO_ROOT / "src" / "expansion_mechanics.c"
ITEMTEST_SRC = REPO_ROOT / "src" / "expansion_itemtest.c"
ITEMTEST_HEADER = REPO_ROOT / "include" / "expansion_itemtest.h"
RUNNER = REPO_ROOT / "tools" / "gba-playtest" / "run_item_expansion_checks.py"

BMITEM_SRC = REPO_ROOT / "src" / "bmitem.c"
ITEMS_EXPANSION_JSON = REPO_ROOT / "src" / "data" / "items_expansion.json"
CONTENT_TEXT_HEADER_NAME = "items_expansion_content_text.h"
CONTENT_TEXT_CATALOG_NAME = "items_expansion_content_text.json"

CC = shutil.which("gcc") or shutil.which("cc")
ARM_CC = shutil.which("arm-none-eabi-gcc")
SIZE = shutil.which("arm-none-eabi-size")
NM = shutil.which("arm-none-eabi-nm")

CONTENT_DEFINES = (
    "FE8_EXPANSION_STARTER_CONTENT=1",
    "FE8_EXPANSION_MECHANICS_HOOKS=1",
    "FE8_EXPANSION_MECHANICS_SAMPLE=1",
    "FE8_ITEM_ID_CAP=0xCE",
)


def authored_name():
    """The ONE authoring source of truth for the bundled content text."""
    import json

    record = json.loads(ITEMS_EXPANSION_JSON.read_text(encoding="utf-8"))["items"][0]
    return record["authoringName"]


def generate_content_text(out_dir, content):
    """Run the real generator exactly as generated_data.mk does."""
    env = dict(os.environ)
    env["EXPANSION_STARTER_CONTENT"] = str(content)
    env["FE8_ITEM_ID_CAP"] = "0xCE"
    return subprocess.run(
        [sys.executable, "-m", "scripts.generated_data", "content-text",
         "--out-dir", str(out_dir)],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)


def _strip_c_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def _include_flags():
    flags = []
    for directory in INCLUDE_DIRS:
        flags += ["-I", str(directory)]
    return flags


def _arm_compile(work_dir, src, obj_name, defines=(), extra_includes=()):
    obj = Path(work_dir) / obj_name
    cmd = [ARM_CC, "-c", "-w", "-std=gnu89", "-mthumb"] + _include_flags()
    cmd += ["-I", str(REPO_ROOT)]
    for directory in extra_includes:
        cmd += ["-I", str(directory)]
    for define in defines:
        cmd += ["-D", define]
    cmd += [str(src), "-o", str(obj)]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr, obj


class SourceHygieneTests(unittest.TestCase):
    """Structural properties that need no toolchain, so they always run."""

    ISSUE6_SOURCES = (
        "src/expansion_starter_content.c",
        "include/expansion_starter_content.h",
        "src/expansion_mechanics.c",
        "include/expansion_mechanics.h",
        "src/expansion_itemtest.c",
    )

    def test_no_raw_numeric_content_item_id(self):
        """The bundled item is always named ITEM_EXPANSION_CE (or reached
        through the typed accessor); a bare 0xCE literal in compiled code
        would silently outlive any future re-numbering.

        String literals are excluded and checked separately below: an
        `#error` that names the exact FE8_ITEM_ID_CAP value to pass is a
        diagnostic, not an ID reference, and dropping it would make the
        failure less actionable."""
        pattern = re.compile(r"\b0[xX]0*CE\b")
        for relative in self.ISSUE6_SOURCES:
            text = _strip_c_comments((REPO_ROOT / relative).read_text(encoding="utf-8"))
            code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
            self.assertIsNone(
                pattern.search(code),
                "{} contains a raw 0xCE item literal; use ITEM_EXPANSION_CE "
                "or ExpansionStarterContentItemId()".format(relative))

    def test_cap_dependency_error_stays_actionable(self):
        """The one permitted 0xCE mention is the #error text that tells the
        contributor exactly which cap to build with."""
        text = CONTENT_HEADER.read_text(encoding="utf-8")
        message = re.search(r'#error "([^"]*expanded item cap[^"]*)"', text)
        self.assertIsNotNone(message)
        self.assertIn("FE8_ITEM_ID_CAP=0xCE", message.group(1))

    def test_no_double_slash_comments(self):
        """Shared C stays C89/agbcc-safe."""
        for relative in self.ISSUE6_SOURCES:
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            without_block = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
            self.assertIsNone(
                re.search(r"(^|[^:])//", without_block),
                "{} contains a // comment".format(relative))

    def test_content_registers_only_through_the_public_api(self):
        text = _strip_c_comments(CONTENT_SRC.read_text(encoding="utf-8"))
        self.assertIn("ExpansionMechanicsRegister(", text)
        for forbidden in ("sEntries", "sCount", "gExpansionMechanicsProbe"):
            self.assertNotIn(
                forbidden, text,
                "the content example must not touch the registry's internals")

    def test_single_builtin_install_point(self):
        """No second router: the content example is installed from the one
        existing ExpansionMechanicsInstallBuiltins() entry point."""
        text = _strip_c_comments(MECHANICS_SRC.read_text(encoding="utf-8"))
        self.assertEqual(text.count("ExpansionStarterContentInstallMechanics()"), 1)
        installs = re.findall(r"void ExpansionMechanicsInstallBuiltins\(void\)", text)
        self.assertEqual(len(installs), 2)  # enabled body + disabled stub

    def test_bmbattle_seam_is_not_content_aware(self):
        """The battle-stat seam must stay generic: no content/item special
        case may leak into src/bmbattle.c."""
        text = _strip_c_comments((REPO_ROOT / "src" / "bmbattle.c").read_text(encoding="utf-8"))
        self.assertNotIn("ExpansionStarterContent", text)
        self.assertNotIn("ITEM_EXPANSION", text)

    def test_content_effect_is_bounded(self):
        header = CONTENT_HEADER.read_text(encoding="utf-8")
        bonus = int(re.search(r"#define EXPANSION_STARTER_CONTENT_AVOID_BONUS\s+(\d+)",
                              header).group(1))
        cap = int(re.search(r"#define EXPANSION_STARTER_CONTENT_AVOID_CAP\s+(\d+)",
                            header).group(1))
        self.assertGreater(bonus, 0)
        self.assertLess(bonus, cap)
        body = _strip_c_comments(CONTENT_SRC.read_text(encoding="utf-8"))
        self.assertIn("EXPANSION_STARTER_CONTENT_AVOID_CAP", body)

    def test_content_stat_differs_from_the_existing_sample(self):
        """The pre-existing content-free sample keeps its own standalone
        semantics: the two built-ins must adjust different stats so both are
        independently observable."""
        content = _strip_c_comments(CONTENT_SRC.read_text(encoding="utf-8"))
        mechanics = _strip_c_comments(MECHANICS_SRC.read_text(encoding="utf-8"))
        self.assertIn("battleAvoidRate", content)
        self.assertNotIn("battleDefense", content)
        self.assertIn("battleDefense", mechanics)

    def test_probe_field_order_matches_the_c_struct(self):
        """run_item_expansion_checks.py reads the probe as base + 4*index, so
        its field list must match struct ItemExpansionProbe exactly."""
        header = ITEMTEST_HEADER.read_text(encoding="utf-8")
        body = header[header.index("struct ItemExpansionProbe"):]
        body = body[:body.index("\n};")]
        body = _strip_c_comments(body)
        fields = re.findall(r"\bu32\s+(\w+)\s*;", body)
        runner = RUNNER.read_text(encoding="utf-8")
        listed = re.search(r"PROBE_FIELDS = \((.*?)\n\)", runner, re.DOTALL).group(1)
        names = re.findall(r'"(\w+)"', listed)
        self.assertEqual(names, fields)

    def test_every_probe_field_is_a_u32_scalar(self):
        """Semantic scalars only -- never a pointer, never a framebuffer."""
        header = ITEMTEST_HEADER.read_text(encoding="utf-8")
        body = header[header.index("struct ItemExpansionProbe"):]
        body = _strip_c_comments(body[:body.index("\n};")])
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("struct") or line == "{":
                continue
            self.assertRegex(line, r"^u32 \w+;$")


@unittest.skipIf(ARM_CC is None or SIZE is None, "no arm-none-eabi toolchain")
class DisabledBuildLayoutTests(unittest.TestCase):
    """A default (content-off) build must add no RAM at all: every committed
    runtime scenario pins absolute EWRAM probe addresses, so a new
    always-linked data object would silently invalidate them."""

    def test_disabled_object_has_no_data_or_bss(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            code, output, obj = _arm_compile(tmp, CONTENT_SRC, "content_off.o")
            self.assertEqual(code, 0, output)
            sizes = subprocess.run([SIZE, "-A", str(obj)], capture_output=True,
                                   text=True, check=True).stdout
            for section in (".data", ".bss", "ewram_data"):
                for line in sizes.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] == section:
                        self.assertEqual(
                            int(parts[1]), 0,
                            "disabled content TU emits {} bytes of {}".format(
                                parts[1], section))


@unittest.skipIf(ARM_CC is None, "no arm-none-eabi toolchain")
class CompileTimeDependencyTests(unittest.TestCase):
    """Both content dependencies are hard compile errors, not warnings."""

    def _compile(self, defines):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            # The content profile also needs the build-local generated text
            # header on the include path (exactly as modern.mk arranges it),
            # so a *dependency* failure below is the dependency's own #error
            # and never a missing-file artefact of the test setup.
            generated = Path(tmp) / "generated"
            self.assertEqual(generate_content_text(generated, 1).returncode, 0)
            return _arm_compile(tmp, CONTENT_SRC, "probe.o", defines, [generated])[:2]

    def test_content_without_hooks_fails(self):
        code, output = self._compile(
            ["FE8_EXPANSION_STARTER_CONTENT=1", "FE8_ITEM_ID_CAP=0xCE"])
        self.assertNotEqual(code, 0)
        self.assertIn("FE8_EXPANSION_MECHANICS_HOOKS=1", output)

    def test_content_at_default_cap_fails(self):
        code, output = self._compile(
            ["FE8_EXPANSION_STARTER_CONTENT=1", "FE8_EXPANSION_MECHANICS_HOOKS=1"])
        self.assertNotEqual(code, 0)
        self.assertIn("expanded item cap", output)

    def test_full_content_profile_compiles(self):
        code, output = self._compile([
            "FE8_EXPANSION_STARTER_CONTENT=1",
            "FE8_EXPANSION_MECHANICS_HOOKS=1",
            "FE8_EXPANSION_MECHANICS_SAMPLE=1",
            "FE8_ITEM_ID_CAP=0xCE",
        ])
        self.assertEqual(code, 0, output)

    def test_default_build_compiles(self):
        code, output = self._compile([])
        self.assertEqual(code, 0, output)


class ContentTextGenerationTests(unittest.TestCase):
    """The ORIGINAL authored display text is generated, config-gated and
    build-local -- never a message appended to the shared, Huffman-compressed
    table (which would re-encode a DEFAULT build's text blob)."""

    def test_default_profile_generates_nothing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            proc = generate_content_text(tmp, 0)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            for name in (CONTENT_TEXT_HEADER_NAME, CONTENT_TEXT_CATALOG_NAME):
                self.assertFalse(
                    (Path(tmp) / name).exists(),
                    "a default build must generate no content text artifact")

    def test_default_profile_removes_a_stale_artifact(self):
        """A previous content build must never leave a string table behind
        for a later default build to pick up."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(generate_content_text(tmp, 1).returncode, 0)
            self.assertTrue((Path(tmp) / CONTENT_TEXT_HEADER_NAME).exists())
            self.assertEqual(generate_content_text(tmp, 0).returncode, 0)
            self.assertFalse((Path(tmp) / CONTENT_TEXT_HEADER_NAME).exists())
            self.assertFalse((Path(tmp) / CONTENT_TEXT_CATALOG_NAME).exists())

    def test_content_profile_emits_the_exact_authored_name(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            proc = generate_content_text(tmp, 1)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            header = (Path(tmp) / CONTENT_TEXT_HEADER_NAME).read_text(encoding="utf-8")
            name = authored_name()
            self.assertIn('"{}"'.format(name), header)
            self.assertIn("ITEM_EXPANSION_CE", header)
            self.assertIn("AUTO-GENERATED", header)

            capacity = int(re.search(
                r"#define EXPANSION_CONTENT_TEXT_NAME_CAPACITY (\d+)", header).group(1))
            self.assertEqual(capacity, len(name) + 1)

            buffer_size = int(re.search(
                r"#define EXPANSION_STARTER_CONTENT_NAME_BUFFER\s+(\d+)",
                CONTENT_HEADER.read_text(encoding="utf-8")).group(1))
            self.assertLessEqual(capacity, buffer_size)

            catalog = json.loads((Path(tmp) / CONTENT_TEXT_CATALOG_NAME).read_text(
                encoding="utf-8"))
            entry = catalog["items"][0]
            self.assertEqual(entry["authoringName"], name)
            self.assertTrue(entry["authoringDescription"])
            self.assertIn("not shown in game", entry["runtimeText"]["description"])

    def test_generated_output_is_deterministic_and_path_independent(self):
        import tempfile

        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self.assertEqual(generate_content_text(one, 1).returncode, 0)
            self.assertEqual(generate_content_text(two, 1).returncode, 0)
            for name in (CONTENT_TEXT_HEADER_NAME, CONTENT_TEXT_CATALOG_NAME):
                first = (Path(one) / name).read_text(encoding="utf-8")
                second = (Path(two) / name).read_text(encoding="utf-8")
                self.assertEqual(first, second)
                self.assertNotIn(str(REPO_ROOT), first)

    def test_no_committed_source_hand_holds_the_authored_text(self):
        """The literal lives in the JSON record and in generated build/
        output only -- never hand-copied into a committed C file."""
        name = authored_name()
        for relative in ("src/expansion_starter_content.c",
                         "include/expansion_starter_content.h",
                         "src/bmitem.c",
                         "src/expansion_itemtest.c"):
            self.assertNotIn(
                name, (REPO_ROOT / relative).read_text(encoding="utf-8"),
                "{} hand-copies the authored content text".format(relative))

    def test_texts_table_carries_no_content_message(self):
        """The regression this whole path exists to prevent."""
        texts = (REPO_ROOT / "texts" / "texts.txt").read_text(
            encoding="utf-8", errors="replace")
        self.assertNotIn("MSG_EXPANSION_", texts)
        msg_header = (REPO_ROOT / "include" / "constants" / "msg.h").read_text(
            encoding="utf-8")
        self.assertNotIn("MSG_EXPANSION_", msg_header)


@unittest.skipIf(ARM_CC is None or NM is None, "no arm-none-eabi toolchain")
class ProductionNamePathTests(unittest.TestCase):
    """src/bmitem.c's GetItemName() -- the ONE function every production item
    name consumer goes through -- reads the authored text in the content
    profile and is preprocessed back to vanilla in a default build."""

    def _symbols(self, obj):
        out = subprocess.run([NM, str(obj)], capture_output=True, text=True,
                             check=True).stdout
        return out

    def test_default_bmitem_has_no_content_seam(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            code, output, obj = _arm_compile(tmp, BMITEM_SRC, "bmitem_off.o")
            self.assertEqual(code, 0, output)
            self.assertNotIn("ExpansionStarterContent", self._symbols(obj))
            self.assertNotIn(authored_name().encode("ascii"), obj.read_bytes())

    def test_content_bmitem_reads_the_typed_accessor(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            generated = Path(tmp) / "generated"
            self.assertEqual(generate_content_text(generated, 1).returncode, 0)
            code, output, obj = _arm_compile(
                tmp, BMITEM_SRC, "bmitem_on.o", CONTENT_DEFINES, [generated])
            self.assertEqual(code, 0, output)
            symbols = self._symbols(obj)
            self.assertIn("U ExpansionStarterContentItemName", symbols)

    def test_content_module_carries_exactly_the_generated_text(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            generated = Path(tmp) / "generated"
            self.assertEqual(generate_content_text(generated, 1).returncode, 0)
            code, output, obj = _arm_compile(
                tmp, CONTENT_SRC, "content_on.o", CONTENT_DEFINES, [generated])
            self.assertEqual(code, 0, output)
            self.assertIn(authored_name().encode("ascii"), obj.read_bytes())
            self.assertIn("T ExpansionStarterContentItemName", self._symbols(obj))

    def test_default_content_module_has_no_authored_text(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            code, output, obj = _arm_compile(tmp, CONTENT_SRC, "content_off.o")
            self.assertEqual(code, 0, output)
            self.assertNotIn(authored_name().encode("ascii"), obj.read_bytes())
            self.assertNotIn("ExpansionStarterContentItemName", self._symbols(obj))

    def test_over_long_authoring_text_fails_the_build(self):
        """The generated capacity is statically asserted against the module's
        buffer, so authoring text that cannot fit is a compile error rather
        than silent truncation on screen."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            generated = Path(tmp) / "generated"
            self.assertEqual(generate_content_text(generated, 1).returncode, 0)
            header = generated / CONTENT_TEXT_HEADER_NAME
            text = header.read_text(encoding="utf-8")
            text = re.sub(r"(#define EXPANSION_CONTENT_TEXT_NAME_CAPACITY )\d+",
                          r"\g<1>999", text)
            header.write_text(text, encoding="utf-8")
            code, output, _ = _arm_compile(
                tmp, CONTENT_SRC, "content_overlong.o", CONTENT_DEFINES, [generated])
            self.assertNotEqual(code, 0)
            self.assertIn("expansion_starter_content_name_fits_buffer", output)


if __name__ == "__main__":
    unittest.main()
