"""
Regression tests for the world-map ``Proc_FindNext()`` iterator NULL guard.

``Proc_FindNext()`` (src/proc.c) returns NULL once a ``ProcFindIterator`` is
exhausted.  Several world-map helpers used to dereference that result *before*
testing it against NULL::

    do
    {
        proc = Proc_FindNext(&procIter);
        if (proc->index == index)   /* NULL dereference on the last iteration */
            return 1;
    } while (proc != NULL);

That is undefined behaviour, and it is not benign.  Because the dereference
happens first, an optimising compiler is entitled to conclude that ``proc``
can never be NULL and to delete the ``while (proc != NULL)`` test -- together
with the loop's only non-``return 1`` exit.  ``arm-none-eabi-gcc -O2`` (the
supported modern *release* configuration) does exactly that: the release build
of ``GmapRmBorder1Exists()`` lost its ``cmp r0, #0`` / ``bne`` exit and could
only ever ``return 1``.

``EventBA_WmRemoveHighlightNationPart2()`` (src/eventscr_gmap.c) does::

    if (!GmapRmBorder1Exists(a))
        return EVC_ADVANCE_YIELD;
    return EVC_STOP_YIELD;

so a ``GmapRmBorder1Exists()`` that can only return 1 makes the world-map
opening event yield forever -- the release ROM hard-locked on a static world
map during the opening tour and never reached a battle map.  The ``-Og`` debug
configuration and the archival agbcc build kept the test and therefore did not
lock, which is why this only ever reproduced on release builds.

These tests pin the fix from both ends: the source-level invariant (never use
the iterator result before the NULL check) and the codegen consequence (the
optimised release build must still be able to leave the loop).
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
INCLUDE_DIRS = [REPO_ROOT / "include", REPO_ROOT / "include" / "generated"]

ARM_CC = shutil.which("arm-none-eabi-gcc")
ARM_OBJDUMP = shutil.which("arm-none-eabi-objdump")

FIND_NEXT_CALL = "= Proc_FindNext(&procIter);"
NULL_GUARD = "if (proc == NULL)"

# The world-map helpers that iterate with Proc_FindNext(). Every one of them
# is reached from the world-map opening tour, so every one of them has to be
# able to terminate on an empty proc list.
GUARDED_FUNCTIONS = {
    "src/worldmap_rm.c": [
        "EndGmapRmBorder1",
        "GmapRmBorder1Exists",
        "RequestGmapRmBorder1Remove",
        "EndWmPlaceDotByIndex",
        "IsWmPlaceDotActiveAtIndex",
        "SetWmPlaceDotFlagForIndex",
    ],
    "src/worldmap_automu.c": [
        "EndGmAutoMuFor",
        "IsGmAutoMuActiveFor",
    ],
}


def _include_flags():
    flags = []
    for path in INCLUDE_DIRS:
        flags += ["-I", str(path)]
    return flags


class ProcFindNextSourceGuardTests(unittest.TestCase):
    """Source invariant: the iterator result is NULL-checked before any use."""

    def test_every_find_next_call_site_is_null_guarded(self):
        offenders = []
        for source in sorted(SRC_DIR.rglob("*.c")):
            lines = source.read_text(encoding="utf-8").split("\n")
            for index, line in enumerate(lines):
                if FIND_NEXT_CALL not in line:
                    continue
                # Look at the next few non-blank lines: the first statement
                # after the call must be the NULL guard.
                following = [
                    text.strip()
                    for text in lines[index + 1:index + 5]
                    if text.strip()
                ]
                if not following or not following[0].startswith(NULL_GUARD):
                    offenders.append(
                        "%s:%d" % (source.relative_to(REPO_ROOT), index + 1))
        self.assertEqual(
            offenders, [],
            "Proc_FindNext() result used before its NULL check at: %s -- the "
            "iterator returns NULL when exhausted, and dereferencing first "
            "lets an optimising compiler delete the loop exit"
            % ", ".join(offenders))

    def test_no_loop_relies_on_a_post_dereference_null_condition(self):
        """`} while (proc != NULL);` after a dereference is the broken shape."""
        offenders = []
        for relative in GUARDED_FUNCTIONS:
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            if "} while (proc != NULL);" in text:
                offenders.append(relative)
        self.assertEqual(
            offenders, [],
            "%s still terminate a Proc_FindNext() loop on a condition the "
            "compiler can prove redundant" % ", ".join(offenders))

    def test_named_helpers_contain_the_guard(self):
        for relative, functions in GUARDED_FUNCTIONS.items():
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            for function in functions:
                match = re.search(
                    r"^[a-zA-Z_].*\b%s\s*\(" % re.escape(function),
                    text, re.MULTILINE)
                self.assertIsNotNone(
                    match, "%s: %s not found" % (relative, function))
                body = text[match.start():match.start() + 1200]
                self.assertIn(
                    FIND_NEXT_CALL, body,
                    "%s: %s no longer iterates with Proc_FindNext()"
                    % (relative, function))
                self.assertIn(
                    NULL_GUARD, body,
                    "%s: %s lost its Proc_FindNext() NULL guard"
                    % (relative, function))


class ProcFindNextCodegenTests(unittest.TestCase):
    """Codegen consequence: -O2 must keep a reachable 'not found' exit."""

    def _compile_o2(self, work_dir, source):
        obj = Path(work_dir) / (source.stem + ".o")
        cmd = [ARM_CC, "-mthumb", "-mcpu=arm7tdmi", "-mabi=aapcs",
               "-std=gnu89", "-O2", "-c", "-w"] + _include_flags() + [
            str(source), "-o", str(obj)]
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT),
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         "arm -O2 compile of %s failed:\n%s"
                         % (source.name, proc.stdout + proc.stderr))
        return obj

    def _disassemble(self, obj, function):
        proc = subprocess.run(
            [ARM_OBJDUMP, "-d", "--disassemble=" + function, str(obj)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         "objdump failed:\n%s" % (proc.stdout + proc.stderr))
        return proc.stdout

    def test_release_build_can_still_leave_the_iterator_loop(self):
        if ARM_CC is None or ARM_OBJDUMP is None:
            raise unittest.SkipTest(
                "arm-none-eabi-gcc/objdump not available")
        with tempfile.TemporaryDirectory() as tmp:
            obj = self._compile_o2(tmp, SRC_DIR / "worldmap_rm.c")
            text = self._disassemble(obj, "GmapRmBorder1Exists")
            self.assertIn(
                "GmapRmBorder1Exists", text,
                "GmapRmBorder1Exists missing from the -O2 object")
            # The "no such proc" answer must survive optimisation. Without the
            # NULL guard, -O2 proved the loop endless and emitted only the
            # `movs r0, #1` answer.
            self.assertIn(
                "#0", text,
                "GmapRmBorder1Exists lost every compare/return against 0 at "
                "-O2: the loop can no longer terminate and the world-map "
                "opening event will yield forever")
            returns_zero = re.search(r"\bmovs?\s+r0,\s*#0\b", text)
            self.assertIsNotNone(
                returns_zero,
                "GmapRmBorder1Exists has no 'return 0' path at -O2; the "
                "undefined-behaviour NULL dereference has come back")


if __name__ == "__main__":
    unittest.main()
