"""Toolchain-free *static* contract queries against modern.mk's make database.

Why this module exists (CI run 30243920318 root cause)
------------------------------------------------------
The debugtools-hub wiring assertions used to shell out to
``make -n <modern goal>`` (e.g. ``expansion-modern-debugtools-check``).  That
looks like a harmless dry run, but every such goal is a member of
``MODERN_ALL_SOURCE_GOALS`` in modern.mk, which gates::

    ifneq (,$(filter $(MODERN_ALL_SOURCE_GOALS),$(MAKECMDGOALS)))
    include $(MODERN_ALL_C_HEADER_DEPS)
    endif

GNU Make remakes *included* makefiles (the per-source ``build/.../*.headers.d``
files) **before** it honours ``-n``.  On a clean checkout those files are
absent, so Make runs the ``%.headers.d: %.c`` recipe for real; that recipe's
order-only ``expansion-modern-toolchain-check`` prerequisite aborts with
``error: modern compiler not found: arm-none-eabi-gcc`` on any lane without the
cross toolchain -- which is exactly the CI ``host-tests`` lane, by design.

The fix is to never name a ``MODERN_ALL_SOURCE_GOALS`` member as a make goal.
This module reads modern.mk's *fully parsed* database with ``make -p`` while
naming only an inert, non-source probe goal, so:

  * ``MAKECMDGOALS`` never matches the header-dep ``ifneq`` gate -> no
    ``.headers.d`` is generated and ``arm-none-eabi-gcc`` is never invoked;
  * every ``ifeq ($(MODERN_CONFIG),...)`` branch, ``:=`` expansion and
    prerequisite list is resolved authoritatively *by make itself* -- no
    drifting copy of modern.mk's recipe text lives here; and
  * it works with an empty build tree and a PATH that has no cross compiler.

The wiring tests assert only on values read out of this database, so they track
modern.mk exactly and raise :class:`ModernMkContractError` (never silently pass)
if its target / recipe / variable structure moves.
"""

from __future__ import annotations

import functools
import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# An inert goal that is deliberately NOT a member of MODERN_ALL_SOURCE_GOALS, so
# naming it as MAKECMDGOALS leaves the header-dependency `include` disabled.
PROBE_GOAL = "__pua_modern_mk_probe__"
_PROBE_MAKEFILE = f"{PROBE_GOAL}:\n\t@:\n.PHONY: {PROBE_GOAL}\n"


class ModernMkContractError(AssertionError):
    """Raised when modern.mk's expected target/recipe/variable is missing.

    Subclasses AssertionError so an unexpected modern.mk structural change
    surfaces as an actionable test failure instead of a silent wrong match.
    """


@functools.lru_cache(maxsize=None)
def query_make_database(config: str) -> str:
    """Return modern.mk's fully parsed ``make -p`` database for ``config``.

    Runs ``make -f Makefile -f - -p -n MODERN_CONFIG=<config> <PROBE_GOAL>`` at
    the repo root with the probe rule fed on stdin.  Because ``PROBE_GOAL`` is
    not a modern *source* goal, no ``*.headers.d`` is remade and no cross
    compiler is required -- the query is safe on a toolchain-free host lane and
    on an empty build tree.  Cached per config (2 invocations at most).
    """
    proc = subprocess.run(
        [
            "make",
            "-f", "Makefile",
            "-f", "-",           # read the inert probe rule from stdin
            "-p",                # dump the parsed database
            "-n",                # never execute the probe's (empty) recipe
            f"MODERN_CONFIG={config}",
            PROBE_GOAL,
        ],
        cwd=REPO_ROOT,
        input=_PROBE_MAKEFILE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ModernMkContractError(
            "`make -p` database query failed for MODERN_CONFIG="
            f"{config!r} (returncode {proc.returncode}). This query must never "
            "need the cross toolchain; a failure here usually means modern.mk / "
            "Makefile changed how goals are read.\n--- stderr ---\n"
            f"{proc.stderr.strip()}"
        )
    return proc.stdout


def variable_value(database: str, name: str) -> str:
    """Return the expanded value make recorded for ``name`` (``NAME := value``).

    The three variables the wiring tests read (``MODERN_DEBUGTOOLS_SRAM_FIXTURE``
    and friends) are all ``:=`` simple variables, so ``make -p`` prints them
    already expanded.
    """
    needle = name + " "
    for line in database.splitlines():
        # Variable lines start at column 0 (recipe lines start with a TAB), so
        # this cannot collide with a recipe body that mentions the same name.
        if line.startswith(needle):
            rest = line[len(name):].lstrip()
            if rest.startswith((":=", "=")):
                return rest.lstrip(":=").lstrip().rstrip()
    raise ModernMkContractError(
        f"variable {name!r} not found in modern.mk make database; the modern.mk "
        "variable contract this test depends on may have changed."
    )


def _rule_start_index(lines: list[str], target: str) -> int:
    exact = target + ":"
    with_prereqs = target + ": "
    for idx, line in enumerate(lines):
        if line == exact or line.startswith(with_prereqs):
            return idx
    raise ModernMkContractError(
        f"target {target!r} not found in modern.mk make database; the modern.mk "
        "target contract this test depends on may have changed."
    )


def rule_prerequisites(database: str, target: str) -> list[str]:
    """Return the (make-expanded) prerequisite list of ``target``."""
    lines = database.splitlines()
    idx = _rule_start_index(lines, target)
    _, _, rest = lines[idx].partition(":")
    return rest.split()


def rule_recipe(database: str, target: str) -> str:
    """Return ``target``'s recipe body exactly as modern.mk defines it.

    Recipe lines are printed verbatim by ``make -p`` (variable references such
    as ``$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)`` are NOT expanded), which is what the
    wiring contract asserts on -- so the assertions mirror modern.mk's source of
    truth rather than a re-derived path string.
    """
    lines = database.splitlines()
    idx = _rule_start_index(lines, target)
    recipe: list[str] = []
    for line in lines[idx + 1:]:
        if line.startswith("#"):
            continue          # make's per-rule annotation comments
        if line.startswith("\t"):
            recipe.append(line[1:])
            continue
        break                 # blank line / next rule terminates the block
    return "\n".join(recipe)


def build_toolchain_free_env(repo_root: Path = REPO_ROOT):
    """Build a hermetic PATH with the host toolset **minus** ``arm-none-eabi-*``.

    Reproduces the CI host-tests lane, where the cross toolchain package is not
    installed, on any machine (including dev boxes / usr-merged distros that DO
    have ``arm-none-eabi-gcc`` in ``/usr/bin``).  Returns ``(env, bin_dir,
    tmp_root)``; the caller removes ``tmp_root`` when done.

    ``env`` also pins ``TOOLCHAIN`` to the hermetic root so the Makefile's
    ``export PATH := $(TOOLCHAIN)/bin:$(PATH)`` line cannot re-add a system bin
    (e.g. ``/bin`` -> ``/usr/bin``) that still holds the cross compiler.
    """
    tmp_root = Path(tempfile.mkdtemp(prefix="pua-toolchain-free-"))
    bin_dir = tmp_root / "bin"
    bin_dir.mkdir(parents=True)
    seen: set[str] = set()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not os.path.isdir(entry):
            continue
        # Skip WSL Windows-interop mounts: huge, irrelevant to a POSIX host
        # toolchain, and absent on real Linux/macOS CI. Keeps this fast.
        if entry.startswith("/mnt/") or os.path.realpath(entry).startswith("/mnt/"):
            continue
        try:
            names = os.listdir(entry)
        except OSError:
            continue
        for name in names:
            if name in seen or name.startswith("arm-none-eabi-"):
                continue
            src = os.path.join(entry, name)
            try:
                if os.access(src, os.X_OK) and not os.path.isdir(src):
                    os.symlink(src, bin_dir / name)
                    seen.add(name)
            except OSError:
                pass
    env = dict(os.environ)
    env["PATH"] = str(bin_dir)
    env["TOOLCHAIN"] = str(tmp_root)   # -> $(TOOLCHAIN)/bin == bin_dir (hermetic)
    for key in ("DEVKITARM", "DEVKITPRO", "MODERN_TOOLCHAIN_ROOT", "MODERN_CC"):
        env.pop(key, None)
    return env, bin_dir, tmp_root
