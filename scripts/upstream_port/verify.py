"""Orchestrate existing repository gates against the CURRENT TRUSTED WORKTREE
after a maintainer has manually applied a port batch.

WARNING (see docs/upstream-porting.md): this command builds and checks the
repository's *own* current working tree/commit. It never builds, checks out,
or executes the canonical upstream ref/tree. It is a thin, literal mirror of
.github/workflows/build.yml's gate steps (kept independent from that file:
this module doesn't parse/execute the workflow, it re-states the same gate
commands so `verify` stays runnable locally without a CI runner).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Sequence


@dataclass
class Gate:
    name: str
    command: List[str]
    applicable_note: str


def gates(jobs: int = 2) -> List[Gate]:
    """Return the ordered gate list, mirroring build.yml's CI steps.

    Kept as data (not hardcoded shell text) so tests can assert on the exact
    command list without actually executing a multi-minute native build.
    """
    return [
        Gate(
            name="artifact-guard",
            command=["python3", "scripts/artifact_guard.py", "--revision", "HEAD"],
            applicable_note="always applicable: rejects prohibited tracked build artifacts",
        ),
        Gate(
            name="default-lane-check",
            command=[
                "python3",
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/modernize/tests",
                "-p",
                "test_build_default_lane.py",
                "-v",
            ],
            applicable_note=(
                "issue #15 closure: asserts a bare `make`/`make all` always "
                "resolves to the modern release AAPCS lane"
            ),
        ),
        Gate(
            name="quickstart-legacy-check",
            command=[
                "python3",
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/modernize/tests",
                "-p",
                "test_quickstart.py",
                "-v",
            ],
            applicable_note=(
                "issue #15 closure: asserts quickstart.sh only reaches the "
                "archival agbcc lane via explicit `make legacy`/`make "
                "fireemblem8.gba`, never via env/CLI variable overrides"
            ),
        ),
        Gate(
            name="generated-data-check",
            command=["make", "generated-data-check"],
            applicable_note="applicable when generated_data.mk-tracked tables exist",
        ),
        Gate(
            name="modern-linker-check-debug",
            command=[
                "make",
                "expansion-modern-linker-check",
                "MODERN_CONFIG=debug",
                "MODERN_ABI=aapcs",
                f"-j{jobs}",
            ],
            applicable_note=(
                "covers modern debug linker + boot + relocation/shift checks "
                "(expansion-modern-linker-check depends on "
                "expansion-modern-boot-check and expansion-modern-shifted-check)"
            ),
        ),
        Gate(
            name="modern-linker-check-release",
            command=[
                "make",
                "expansion-modern-linker-check",
                "MODERN_CONFIG=release",
                "MODERN_ABI=aapcs",
                f"-j{jobs}",
            ],
            applicable_note="release-config counterpart of the debug gate above",
        ),
    ]


@dataclass
class GateResult:
    gate: Gate
    ran: bool
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.ran and self.returncode == 0


def run_gates(cwd: str, jobs: int = 2, dry_run: bool = False, selected: Sequence[str] = ()) -> List[GateResult]:
    """Execute (or, if dry_run, just describe) each applicable gate in order.

    Stops at the first failing gate (fail-fast, matching CI). Never weakens,
    reorders, or skips a gate silently -- `selected` (if non-empty) restricts
    to those gate names, and any resulting skip is reported explicitly by the
    caller via the gate names actually returned.
    """
    results: List[GateResult] = []
    for gate in gates(jobs=jobs):
        if selected and gate.name not in selected:
            continue
        if dry_run:
            results.append(GateResult(gate=gate, ran=False, returncode=0, stdout="", stderr=""))
            continue
        proc = subprocess.run(
            gate.command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        result = GateResult(
            gate=gate,
            ran=True,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
        results.append(result)
        if not result.passed:
            break
    return results
