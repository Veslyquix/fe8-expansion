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
from typing import List


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
            name="gba-playtest-host-suite",
            command=[
                "python3",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tools/gba-playtest/tests",
                "-v",
            ],
            applicable_note=(
                "issue #13 host lane (build.yml `host-tests` job, textually "
                "first): every tools/gba-playtest host test -- scenario/schema "
                "parsing, generators, config, save/migration fixtures, "
                "timeouts, retry policy, deterministic sorted-JSON output, "
                "provenance/diagnostics. Host-only (build-essential + "
                "libmgba-dev, no arm-none-eabi toolchain); never builds/links "
                "the ROM, so it does not overlap the modern-linker gates below"
            ),
        ),
        Gate(
            name="upstream-port-tests",
            command=[
                "python3",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests/upstream_port",
                "-v",
            ],
            applicable_note=(
                "issue #12/#15 host lane (same `host-tests` job): the 139 "
                "pure-stdlib upstream-port review tooling tests "
                "(classify/scan/drift/state/ref-binding/output-safety/"
                "merge-commit determinism and this verify.gates() <-> build.yml "
                "mirror). Python/stdlib only, links no C and never rebuilds the "
                "ROM"
            ),
        ),
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
                "aggregates the full modern DEBUG ROM/ELF runtime + linker "
                "suite off a single reused object/ELF build -- the runtime "
                "scenarios are covered here and are NOT re-run individually by "
                "verify, so no gate triggers a second/redundant ROM build. "
                "expansion-modern-linker-check depends on -budget-check, "
                "-overlay-audit (-> -relocs), -boot-check, -title-check, "
                "-debugtools-check/-timer-check/-map-check/-tools-check, "
                "-debugtools-prep-check, -debugtools-ch4prep-check, "
                "-newgame-check, -combat-check, -saveload-check (incl. the "
                "suspend/resume save scenario), -savefmt-check (save-format "
                "migration) and -shifted-check, then runs the shift/offset "
                "address scan and the raw-pointer cast audit. Net coverage: "
                "boot, title, new-game, map, prep, combat, save-load, "
                "suspend/resume, debugtools-tools, save migration, budget, "
                "shift/offset, raw-pointer, relocation and cross-overlay"
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
            applicable_note=(
                "release-config counterpart of the debug gate above: the same "
                "aggregated runtime + linker suite off the reused RELEASE "
                "object/ELF build, additionally exercising the release "
                "debugtools-disabled negative scenarios. Runtime scenarios are "
                "covered here, not re-run individually by verify"
            ),
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


def run_gates(cwd: str, jobs: int = 2, dry_run: bool = False) -> List[GateResult]:
    """Execute (or, if dry_run, just describe) every gate, in the fixed
    order returned by `gates()`.

    Stops at the first failing gate (fail-fast, matching CI). Never
    weakens, reorders, or skips a gate. There is intentionally no gate
    *selection* capability here (no `selected`/subset parameter): closure
    evidence for this tool is only ever the full, ordered gate set --
    partial/unknown/zero-gate "success" is a forged closure signal, not a
    real one. (See docs/upstream-porting.md and cli.py -- the public
    `verify` subcommand has no `--gate` flag for the same reason; this
    function has no internal escape hatch a caller could use to bypass
    that either.)
    """
    results: List[GateResult] = []
    for gate in gates(jobs=jobs):
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
