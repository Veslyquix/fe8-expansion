#!/usr/bin/env python3
"""Deterministic, headless GBA scenario capture and verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCENARIO_SCHEMA_VERSION = 1
FINGERPRINT_FORMAT_VERSION = 2
PKG_CONFIG_TIMEOUT_SECONDS = 10
COMPILER_TIMEOUT_SECONDS = 60
MIN_BACKEND_TIMEOUT_SECONDS = 10
MAX_BACKEND_TIMEOUT_SECONDS = 300
# Hard ceiling on --retries regardless of the caller-requested value, so a
# typo or a misguided "just retry more" edit can never turn this into an
# unbounded/effectively-silent retry loop. 0 (the default everywhere) means
# exactly one attempt -- retrying is always an explicit, capped opt-in.
MAX_RETRIES_CAP = 5
KEY_BITS = {
    "A": 1 << 0,
    "B": 1 << 1,
    "SELECT": 1 << 2,
    "START": 1 << 3,
    "RIGHT": 1 << 4,
    "LEFT": 1 << 5,
    "UP": 1 << 6,
    "DOWN": 1 << 7,
    "R": 1 << 8,
    "L": 1 << 9,
}
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
HEX_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{8}$")
HASH_RE = re.compile(r"^fnv1a64-rgb24:[0-9a-f]{16}$")
# "fnv1a64-sram:" is the exact whole-0x8000-byte hash (default, required for
# any checkpoint that must prove byte-for-byte SRAM preservation, e.g. the
# non-destructive Back scenarios). "fnv1a64-sram-normalized:" is the same
# FNV-1a construction with `sram_hash_exclude_ranges` bytes skipped -- used
# only for checkpoints whose SRAM is expected to contain intentionally
# build-variable diagnostic bytes (see docs/save_format.md's "SRAM hash
# policy: exact vs. normalized" section). The algorithm name in the hash
# text always identifies which policy produced it.
SRAM_HASH_RE = re.compile(r"^fnv1a64-sram(?:-normalized)?:[0-9a-f]{16}$")
RAM_RANGES = ((0x02000000, 0x02040000), (0x03000000, 0x03008000), (0x0E000000, 0x0E008000))
SRAM_IMAGE_SIZE = 0x8000
# Matches backend.c's read_plan() rejection of checkpoint->exclude_range_count
# > 64 -- validated here too so a scenario with too many ranges fails fast
# with a clear PlaytestError instead of being rejected deep inside the
# backend after a plan file has already been generated.
MAX_SRAM_HASH_EXCLUDE_RANGES = 64


class PlaytestError(Exception):
    """A user-actionable setup or input error."""


class DuplicateKeyError(ValueError):
    pass


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PlaytestError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=_object_no_duplicates)
    except (json.JSONDecodeError, DuplicateKeyError) as exc:
        raise PlaytestError(f"invalid JSON in {path}: {exc}") from exc


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _expect_object(
    value: Any, path: str, required: set[str], optional: set[str] = frozenset()
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlaytestError(f"{path} must be an object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required - optional)
    if missing:
        raise PlaytestError(f"{path} is missing required field(s): {', '.join(missing)}")
    if unknown:
        raise PlaytestError(f"{path} has unknown field(s): {', '.join(unknown)}")
    return value


def _expect_name(value: Any, path: str) -> str:
    if not isinstance(value, str) or not NAME_RE.fullmatch(value):
        raise PlaytestError(
            f"{path} must match {NAME_RE.pattern!r} (1-64 ASCII characters)"
        )
    return value


def _expect_frame(value: Any, path: str) -> int:
    if not _is_int(value) or value < 0 or value > 10_000_000:
        raise PlaytestError(f"{path} must be an integer from 0 through 10000000")
    return value


def _parse_address(value: Any, size: int, path: str) -> int:
    if not isinstance(value, str) or not HEX_ADDRESS_RE.fullmatch(value):
        raise PlaytestError(f"{path} must be an 8-digit hexadecimal string such as 0x02000000")
    address = int(value, 16)
    containing = next(
        ((start, end) for start, end in RAM_RANGES if start <= address < end),
        None,
    )
    if containing is None:
        raise PlaytestError(
            f"{path} must be in EWRAM 0x02000000-0x0203ffff, IWRAM 0x03000000-0x03007fff, "
            "or cart SRAM 0x0e000000-0x0e007fff"
        )
    _, end = containing
    if address + size > end:
        raise PlaytestError(f"{path} plus size {size} crosses the RAM region boundary")
    if address % size:
        raise PlaytestError(f"{path} must be aligned to probe size {size}")
    return address


@dataclass(frozen=True)
class InputRange:
    start: int
    end: int
    key_mask: int


@dataclass(frozen=True)
class Probe:
    address: int
    size: int
    expected: str | None


@dataclass(frozen=True)
class Checkpoint:
    name: str
    frame: int
    framebuffer: bool
    expected_framebuffer_hash: str | None
    sram_hash: bool
    expected_sram_hash: str | None
    # Byte ranges within the 0x8000-byte SRAM image excluded from
    # `sram_hash`'s computation (each an (offset, length) pair, ascending
    # and non-overlapping). Empty means the exact whole-image hash;
    # non-empty selects the normalized ("fnv1a64-sram-normalized:") hash --
    # see docs/save_format.md's "SRAM hash policy: exact vs. normalized".
    sram_hash_exclude_ranges: tuple[tuple[int, int], ...]
    probes: tuple[Probe, ...]


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    disabled: bool
    blocker: str | None
    inputs: tuple[InputRange, ...]
    checkpoints: tuple[Checkpoint, ...]


def parse_scenario_data(data: Any, source: str = "<scenario>") -> Scenario:
    root = _expect_object(
        data,
        source,
        {"schema_version", "name", "frames", "checkpoints"},
        {"description", "disabled", "blocker"},
    )
    if (
        not _is_int(root["schema_version"])
        or root["schema_version"] != SCENARIO_SCHEMA_VERSION
    ):
        raise PlaytestError(
            f"{source}.schema_version must be integer {SCENARIO_SCHEMA_VERSION}"
        )
    name = _expect_name(root["name"], f"{source}.name")
    description = root.get("description", "")
    if not isinstance(description, str):
        raise PlaytestError(f"{source}.description must be a string")
    disabled = root.get("disabled", False)
    if not isinstance(disabled, bool):
        raise PlaytestError(f"{source}.disabled must be a boolean")
    blocker = root.get("blocker")
    if blocker is not None and (not isinstance(blocker, str) or not blocker.strip()):
        raise PlaytestError(f"{source}.blocker must be a non-empty string")
    if disabled and not blocker:
        raise PlaytestError(f"{source}.blocker is required when disabled is true")
    if not disabled and blocker is not None:
        raise PlaytestError(f"{source}.blocker is only allowed when disabled is true")

    frames_data = root["frames"]
    if not isinstance(frames_data, list):
        raise PlaytestError(f"{source}.frames must be an array")
    inputs: list[InputRange] = []
    previous_end = -1
    for index, raw in enumerate(frames_data):
        path = f"{source}.frames[{index}]"
        item = _expect_object(raw, path, {"start", "end", "keys"})
        start = _expect_frame(item["start"], f"{path}.start")
        end = _expect_frame(item["end"], f"{path}.end")
        if end < start:
            raise PlaytestError(f"{path}.end must be greater than or equal to start")
        if start <= previous_end:
            raise PlaytestError(f"{path} overlaps or is not ordered after the previous frame range")
        keys = item["keys"]
        if not isinstance(keys, list):
            raise PlaytestError(f"{path}.keys must be an array")
        if not all(isinstance(key, str) for key in keys):
            raise PlaytestError(f"{path}.keys must contain only string key names")
        if len(keys) != len(set(keys)):
            raise PlaytestError(f"{path}.keys must contain unique key names")
        invalid = [key for key in keys if key not in KEY_BITS]
        if invalid:
            rendered = ", ".join(repr(key) for key in invalid)
            raise PlaytestError(
                f"{path}.keys contains invalid key name(s): {rendered}; "
                f"valid names: {', '.join(KEY_BITS)}"
            )
        mask = 0
        for key in keys:
            mask |= KEY_BITS[key]
        inputs.append(InputRange(start, end, mask))
        previous_end = end

    checkpoints_data = root["checkpoints"]
    if not isinstance(checkpoints_data, list):
        raise PlaytestError(f"{source}.checkpoints must be an array")
    if not disabled and not checkpoints_data:
        raise PlaytestError(f"{source}.checkpoints must not be empty for an active scenario")
    checkpoints: list[Checkpoint] = []
    checkpoint_names: set[str] = set()
    checkpoint_frames: set[int] = set()
    for index, raw in enumerate(checkpoints_data):
        path = f"{source}.checkpoints[{index}]"
        item = _expect_object(
            raw,
            path,
            {"name", "frame", "framebuffer", "probes"},
            {
                "expected_framebuffer_hash",
                "sram_hash",
                "expected_sram_hash",
                "sram_hash_exclude_ranges",
            },
        )
        checkpoint_name = _expect_name(item["name"], f"{path}.name")
        if checkpoint_name in checkpoint_names:
            raise PlaytestError(f"{path}.name duplicates checkpoint {checkpoint_name!r}")
        checkpoint_names.add(checkpoint_name)
        frame = _expect_frame(item["frame"], f"{path}.frame")
        if frame in checkpoint_frames:
            raise PlaytestError(f"{path}.frame duplicates checkpoint frame {frame}")
        checkpoint_frames.add(frame)
        framebuffer = item["framebuffer"]
        if not isinstance(framebuffer, bool):
            raise PlaytestError(f"{path}.framebuffer must be a boolean")
        expected_hash = item.get("expected_framebuffer_hash")
        if expected_hash is not None and (
            not isinstance(expected_hash, str) or not HASH_RE.fullmatch(expected_hash)
        ):
            raise PlaytestError(
                f"{path}.expected_framebuffer_hash must look like "
                "'fnv1a64-rgb24:0123456789abcdef'"
            )
        if expected_hash is not None and not framebuffer:
            raise PlaytestError(f"{path}.expected_framebuffer_hash requires framebuffer true")
        sram_hash = item.get("sram_hash", False)
        if not isinstance(sram_hash, bool):
            raise PlaytestError(f"{path}.sram_hash must be a boolean")
        expected_sram_hash = item.get("expected_sram_hash")
        if expected_sram_hash is not None and (
            not isinstance(expected_sram_hash, str)
            or not SRAM_HASH_RE.fullmatch(expected_sram_hash)
        ):
            raise PlaytestError(
                f"{path}.expected_sram_hash must look like "
                "'fnv1a64-sram:0123456789abcdef'"
            )
        if expected_sram_hash is not None and not sram_hash:
            raise PlaytestError(f"{path}.expected_sram_hash requires sram_hash true")
        exclude_ranges_data = item.get("sram_hash_exclude_ranges")
        sram_hash_exclude_ranges: list[tuple[int, int]] = []
        if exclude_ranges_data is not None:
            if not sram_hash:
                raise PlaytestError(f"{path}.sram_hash_exclude_ranges requires sram_hash true")
            if not isinstance(exclude_ranges_data, list) or not exclude_ranges_data:
                raise PlaytestError(f"{path}.sram_hash_exclude_ranges must be a non-empty array")
            if len(exclude_ranges_data) > MAX_SRAM_HASH_EXCLUDE_RANGES:
                raise PlaytestError(
                    f"{path}.sram_hash_exclude_ranges for checkpoint {checkpoint_name!r} has "
                    f"{len(exclude_ranges_data)} ranges, exceeding the "
                    f"{MAX_SRAM_HASH_EXCLUDE_RANGES}-range limit per checkpoint "
                    "(matches backend.c's plan-format cap)"
                )
            previous_range_end = -1
            for range_index, raw_range in enumerate(exclude_ranges_data):
                range_path = f"{path}.sram_hash_exclude_ranges[{range_index}]"
                range_item = _expect_object(raw_range, range_path, {"offset", "length"})
                offset = range_item["offset"]
                length = range_item["length"]
                if not _is_int(offset) or offset < 0 or offset >= SRAM_IMAGE_SIZE:
                    raise PlaytestError(
                        f"{range_path}.offset must be an integer from 0 through "
                        f"{SRAM_IMAGE_SIZE - 1}"
                    )
                if not _is_int(length) or length < 1 or length > SRAM_IMAGE_SIZE:
                    raise PlaytestError(
                        f"{range_path}.length must be an integer from 1 through {SRAM_IMAGE_SIZE}"
                    )
                if offset + length > SRAM_IMAGE_SIZE:
                    raise PlaytestError(
                        f"{range_path} (offset {offset} + length {length}) exceeds the "
                        f"{SRAM_IMAGE_SIZE}-byte SRAM image"
                    )
                if offset <= previous_range_end:
                    raise PlaytestError(
                        f"{range_path} overlaps or is not ordered strictly after the "
                        "previous exclude range"
                    )
                previous_range_end = offset + length - 1
                sram_hash_exclude_ranges.append((offset, length))
        probes_data = item["probes"]
        if not isinstance(probes_data, list):
            raise PlaytestError(f"{path}.probes must be an array")
        probes: list[Probe] = []
        seen_probes: set[tuple[int, int]] = set()
        for probe_index, raw_probe in enumerate(probes_data):
            probe_path = f"{path}.probes[{probe_index}]"
            probe_data = _expect_object(
                raw_probe, probe_path, {"address", "size"}, {"expected"}
            )
            size = probe_data["size"]
            if not _is_int(size) or size not in (1, 2, 4):
                raise PlaytestError(f"{probe_path}.size must be integer 1, 2, or 4")
            address = _parse_address(probe_data["address"], size, f"{probe_path}.address")
            identity = (address, size)
            if identity in seen_probes:
                raise PlaytestError(f"{probe_path} duplicates address/size in this checkpoint")
            seen_probes.add(identity)
            expected = probe_data.get("expected")
            if expected is not None:
                pattern = re.compile(rf"^0x[0-9a-f]{{{size * 2}}}$")
                if not isinstance(expected, str) or not pattern.fullmatch(expected):
                    raise PlaytestError(
                        f"{probe_path}.expected must be lowercase 0x plus {size * 2} hex digits"
                    )
            probes.append(Probe(address, size, expected))
        if not framebuffer and not probes and not sram_hash:
            raise PlaytestError(
                f"{path} must capture a framebuffer, sram_hash, or at least one probe"
            )
        checkpoints.append(
            Checkpoint(
                checkpoint_name,
                frame,
                framebuffer,
                expected_hash,
                sram_hash,
                expected_sram_hash,
                tuple(sram_hash_exclude_ranges),
                tuple(sorted(probes, key=lambda probe: (probe.address, probe.size))),
            )
        )
    if not disabled and inputs:
        last_checkpoint_frame = max(checkpoint.frame for checkpoint in checkpoints)
        if inputs[-1].end > last_checkpoint_frame:
            raise PlaytestError(
                f"{source}.frames[-1].end is after the final checkpoint frame "
                f"{last_checkpoint_frame}"
            )
    return Scenario(
        name,
        description,
        disabled,
        blocker,
        tuple(inputs),
        tuple(sorted(checkpoints, key=lambda checkpoint: (checkpoint.frame, checkpoint.name))),
    )


def load_scenario(path: Path) -> Scenario:
    return parse_scenario_data(_read_json(path), str(path))


def serialize_fingerprint(fingerprint: dict[str, Any]) -> str:
    return json.dumps(fingerprint, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _header_text(raw: bytes) -> str:
    raw = raw.rstrip(b"\x00 ")
    return "".join(
        chr(byte) if 0x20 <= byte <= 0x7E else f"\\x{byte:02x}" for byte in raw
    )


def rom_provenance(path: Path) -> dict[str, Any]:
    digest = hashlib.sha1()
    try:
        size = path.stat().st_size
        with path.open("rb") as rom:
            header = rom.read(0xB0)
            digest.update(header)
            while chunk := rom.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise PlaytestError(f"cannot fingerprint ROM {path}: {exc}") from exc
    if len(header) < 0xB0:
        raise PlaytestError(f"ROM is too small to contain a GBA header: {path}")
    return {
        "game_code": _header_text(header[0xAC:0xB0]),
        "sha1": digest.hexdigest(),
        "size": size,
        "title": _header_text(header[0xA0:0xAC]),
    }


def _bounded_retry_count(retries: int) -> int:
    """Clamps a caller-requested retry count into [0, MAX_RETRIES_CAP]."""
    return max(0, min(retries, MAX_RETRIES_CAP))


def _run_transient_retryable(
    command: list[str], *, timeout: float, retries: int, operation: str
) -> subprocess.CompletedProcess[str]:
    """Runs `command`, retrying only a process time-out -- the one condition
    here that can plausibly be transient host scheduling/load rather than a
    deterministic outcome. A non-zero exit code is returned as-is (the
    caller decides what it means) and is never retried here, and callers
    must never retry a fingerprint mismatch or malformed-output diagnostic
    either: retrying those would silently launder a real, reproducible
    failure into intermittent-looking flake. `retries` is bounded by
    `MAX_RETRIES_CAP` regardless of the caller-supplied value. Every timed
    out attempt that will be retried is reported on stderr with its 1-based
    attempt number out of the total planned attempts, so a flaky time out
    is always visible in the log even when a later attempt succeeds; the
    final attempt's time-out is left for the caller to turn into an
    actionable `PlaytestError` exactly as before (naming the same total
    attempt count).
    """
    attempts = _bounded_retry_count(retries) + 1
    for attempt in range(1, attempts + 1):
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            if attempt >= attempts:
                raise
            print(
                f"gba-playtest: {operation} attempt {attempt}/{attempts} timed out "
                f"after {timeout:g}s -- retrying (transient timeout only; a "
                "non-zero exit or mismatched/malformed output is never retried)",
                file=sys.stderr,
            )
    raise AssertionError("unreachable: loop always returns or raises")


def _compiler_command(
    source: Path, output: Path, retries: int = 0
) -> list[str]:
    cc = os.environ.get("CC", "cc")
    if not shutil.which(cc):
        raise PlaytestError(f"libmGBA backend unavailable: C compiler {cc!r} was not found")
    command = [
        cc,
        "-std=gnu11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        str(source),
        "-o",
        str(output),
    ]
    pkg_config = shutil.which("pkg-config")
    if pkg_config:
        try:
            flags = _run_transient_retryable(
                [pkg_config, "--cflags", "--libs", "mgba"],
                timeout=PKG_CONFIG_TIMEOUT_SECONDS,
                retries=retries,
                operation="pkg-config",
            )
        except subprocess.TimeoutExpired as exc:
            attempts = _bounded_retry_count(retries) + 1
            raise PlaytestError(
                f"pkg-config timed out after {PKG_CONFIG_TIMEOUT_SECONDS}s "
                f"while locating libmGBA (attempt {attempts}/{attempts}, "
                "no attempts remaining)"
            ) from exc
        if flags.returncode == 0:
            import shlex

            command.extend(shlex.split(flags.stdout))
            return command
    command.append("-lmgba")
    return command


def build_backend(output: Path, retries: int = 0) -> None:
    source = Path(__file__).with_name("backend.c")
    command = _compiler_command(source, output, retries)
    try:
        result = _run_transient_retryable(
            command,
            timeout=COMPILER_TIMEOUT_SECONDS,
            retries=retries,
            operation="libmGBA backend compilation",
        )
    except subprocess.TimeoutExpired as exc:
        attempts = _bounded_retry_count(retries) + 1
        raise PlaytestError(
            f"libmGBA backend compilation timed out after "
            f"{COMPILER_TIMEOUT_SECONDS}s (attempt {attempts}/{attempts}, "
            "no attempts remaining)"
        ) from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "compiler returned no diagnostics"
        raise PlaytestError(
            "libmGBA backend unavailable: compilation failed.\n"
            "Install libmGBA development headers (Linux: libmgba-dev; macOS: brew install mgba).\n"
            f"Compiler diagnostic:\n{detail}"
        )


def _write_plan(path: Path, scenario: Scenario) -> None:
    # Plan format version 2 adds a per-checkpoint SRAM-hash-exclude-range
    # count/list (before the probe list) to support
    # `sram_hash_exclude_ranges`. This plan file is generated and consumed
    # within the same `capture()`/`verify` invocation only (never persisted
    # across gba_playtest.py/backend.c versions), so there is no backward
    # compatibility to preserve here -- backend.c's read_plan() is updated
    # in lockstep.
    lines = ["GBA_PLAYTEST_PLAN 2", f"RANGES {len(scenario.inputs)}"]
    lines.extend(
        f"{frame_range.start} {frame_range.end} {frame_range.key_mask}"
        for frame_range in scenario.inputs
    )
    lines.append(f"CHECKPOINTS {len(scenario.checkpoints)}")
    for checkpoint in scenario.checkpoints:
        lines.append(
            f"{checkpoint.frame} {len(checkpoint.probes)} {int(checkpoint.sram_hash)} "
            f"{len(checkpoint.sram_hash_exclude_ranges)}"
        )
        lines.extend(
            f"{offset} {length}"
            for offset, length in checkpoint.sram_hash_exclude_ranges
        )
        lines.extend(f"{probe.address} {probe.size}" for probe in checkpoint.probes)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _parse_backend_output(stdout: str, scenario: Scenario) -> dict[str, Any]:
    hashes: dict[int, str] = {}
    sram_hashes: dict[int, str] = {}
    values: dict[tuple[int, int], int] = {}
    for line_number, line in enumerate(stdout.splitlines(), 1):
        fields = line.split("\t")
        try:
            if len(fields) == 4 and fields[0] == "CHECKPOINT":
                checkpoint_index = int(fields[1])
                frame = int(fields[2])
                if checkpoint_index in hashes:
                    raise ValueError("duplicate checkpoint")
                if not (0 <= checkpoint_index < len(scenario.checkpoints)):
                    raise ValueError("checkpoint index out of range")
                if frame != scenario.checkpoints[checkpoint_index].frame:
                    raise ValueError("checkpoint frame does not match plan")
                if not re.fullmatch(r"[0-9a-f]{16}", fields[3]):
                    raise ValueError("malformed hash")
                hashes[checkpoint_index] = f"fnv1a64-rgb24:{fields[3]}"
            elif len(fields) == 3 and fields[0] == "SRAMHASH":
                checkpoint_index = int(fields[1])
                if checkpoint_index in sram_hashes:
                    raise ValueError("duplicate sram hash")
                if not (0 <= checkpoint_index < len(scenario.checkpoints)):
                    raise ValueError("sram hash checkpoint index out of range")
                sram_checkpoint = scenario.checkpoints[checkpoint_index]
                if not sram_checkpoint.sram_hash:
                    raise ValueError("unexpected sram hash for checkpoint without sram_hash")
                if not re.fullmatch(r"[0-9a-f]{16}", fields[2]):
                    raise ValueError("malformed sram hash")
                # The algorithm name always identifies whether any bytes
                # were excluded, so "exact" and "normalized" hashes can
                # never be silently confused with each other downstream.
                algorithm = (
                    "fnv1a64-sram-normalized"
                    if sram_checkpoint.sram_hash_exclude_ranges
                    else "fnv1a64-sram"
                )
                sram_hashes[checkpoint_index] = f"{algorithm}:{fields[2]}"
            elif len(fields) == 4 and fields[0] == "PROBE":
                checkpoint_index = int(fields[1])
                probe_index = int(fields[2])
                value = int(fields[3])
                identity = (checkpoint_index, probe_index)
                if identity in values:
                    raise ValueError("duplicate probe")
                if not (0 <= checkpoint_index < len(scenario.checkpoints)):
                    raise ValueError("probe checkpoint index out of range")
                if not (0 <= probe_index < len(scenario.checkpoints[checkpoint_index].probes)):
                    raise ValueError("probe index out of range")
                values[identity] = value
            else:
                raise ValueError("unknown record")
        except ValueError as exc:
            raise PlaytestError(
                f"malformed backend output at line {line_number}: {line!r} ({exc})"
            ) from exc
    if len(hashes) != len(scenario.checkpoints):
        raise PlaytestError(
            f"backend returned {len(hashes)} of {len(scenario.checkpoints)} checkpoints"
        )
    expected_sram_hash_count = sum(
        1 for checkpoint in scenario.checkpoints if checkpoint.sram_hash
    )
    if len(sram_hashes) != expected_sram_hash_count:
        raise PlaytestError(
            f"backend returned {len(sram_hashes)} of {expected_sram_hash_count} SRAM hashes"
        )
    expected_probe_count = sum(len(checkpoint.probes) for checkpoint in scenario.checkpoints)
    if len(values) != expected_probe_count:
        raise PlaytestError(
            f"backend returned {len(values)} of {expected_probe_count} probes"
        )
    checkpoints: list[dict[str, Any]] = []
    for checkpoint_index, checkpoint in enumerate(scenario.checkpoints):
        captured: dict[str, Any] = {
            "frame": checkpoint.frame,
            "name": checkpoint.name,
            "probes": [],
        }
        if checkpoint.framebuffer:
            captured["framebuffer_hash"] = hashes[checkpoint_index]
        if checkpoint.sram_hash:
            captured["sram_hash"] = sram_hashes[checkpoint_index]
        captured["probes"] = [
            {
                "address": f"0x{probe.address:08x}",
                "size": probe.size,
                "value": f"0x{values[(checkpoint_index, probe_index)]:0{probe.size * 2}x}",
            }
            for probe_index, probe in enumerate(checkpoint.probes)
        ]
        checkpoints.append(captured)
    return {
        "checkpoints": checkpoints,
        "format_version": FINGERPRINT_FORMAT_VERSION,
        "scenario": scenario.name,
    }


def capture(
    rom: Path,
    scenario: Scenario,
    sram_image: Path | None = None,
    retries: int = 0,
) -> dict[str, Any]:
    if scenario.disabled:
        raise PlaytestError(f"scenario {scenario.name!r} is disabled: {scenario.blocker}")
    if not rom.is_file():
        raise PlaytestError(f"ROM does not exist or is not a regular file: {rom}")
    if sram_image is not None:
        if not sram_image.is_file():
            raise PlaytestError(f"SRAM image does not exist or is not a regular file: {sram_image}")
        actual_size = sram_image.stat().st_size
        if actual_size != SRAM_IMAGE_SIZE:
            raise PlaytestError(
                f"SRAM image {sram_image} must be exactly {SRAM_IMAGE_SIZE} (0x8000) bytes, "
                f"got {actual_size}"
            )
    with tempfile.TemporaryDirectory(prefix="gba-playtest-") as temporary:
        temporary_path = Path(temporary)
        backend = temporary_path / "gba-playtest-backend"
        plan = temporary_path / "plan.txt"
        execution_rom = temporary_path / "input.gba"
        try:
            shutil.copyfile(rom, execution_rom)
            execution_rom.chmod(0o400)
        except OSError as exc:
            raise PlaytestError(f"cannot stage ROM {rom} for deterministic execution: {exc}") from exc
        execution_sram: Path | None = None
        if sram_image is not None:
            execution_sram = temporary_path / "input.sav"
            try:
                shutil.copyfile(sram_image, execution_sram)
                # Left writable (unlike the ROM copy above): libmGBA opens
                # save data read-write since gameplay may legitimately
                # write to it, and this is a disposable temporary copy the
                # original sram_image is never mutated through.
            except OSError as exc:
                raise PlaytestError(
                    f"cannot stage SRAM image {sram_image} for deterministic execution: {exc}"
                ) from exc
        # The identity is computed from the immutable temporary copy passed to
        # libmGBA, avoiding a path-replacement race between hashing and loading.
        provenance = rom_provenance(execution_rom)
        build_backend(backend, retries)
        _write_plan(plan, scenario)
        last_frame = scenario.checkpoints[-1].frame
        backend_timeout = min(
            MAX_BACKEND_TIMEOUT_SECONDS,
            max(MIN_BACKEND_TIMEOUT_SECONDS, 10 + last_frame / 30),
        )
        backend_args = [str(backend), str(execution_rom), str(plan)]
        if execution_sram is not None:
            backend_args.append(str(execution_sram))
        try:
            result = _run_transient_retryable(
                backend_args,
                timeout=backend_timeout,
                retries=retries,
                operation="libmGBA backend",
            )
        except subprocess.TimeoutExpired as exc:
            attempts = _bounded_retry_count(retries) + 1
            raise PlaytestError(
                f"libmGBA backend timed out after {backend_timeout:g}s "
                f"while running through frame {last_frame} "
                f"(attempt {attempts}/{attempts}, no attempts remaining)"
            ) from exc
        if result.returncode:
            diagnostic = result.stderr.strip() or "backend returned no diagnostic"
            raise PlaytestError(
                f"libmGBA backend failed with exit {result.returncode}: {diagnostic}"
            )
        fingerprint = _parse_backend_output(result.stdout, scenario)
        fingerprint["rom"] = provenance
    inline_differences = compare_inline_expectations(scenario, fingerprint)
    if inline_differences:
        raise PlaytestError(
            "scenario inline expectation mismatch:\n"
            + "\n".join(f"  - {difference}" for difference in inline_differences)
        )
    return fingerprint


def compare_inline_expectations(
    scenario: Scenario, fingerprint: dict[str, Any]
) -> list[str]:
    differences: list[str] = []
    actual_checkpoints = fingerprint["checkpoints"]
    for checkpoint, actual in zip(scenario.checkpoints, actual_checkpoints):
        prefix = f"checkpoint {checkpoint.name!r} (frame {checkpoint.frame})"
        if (
            checkpoint.expected_framebuffer_hash is not None
            and actual.get("framebuffer_hash") != checkpoint.expected_framebuffer_hash
        ):
            differences.append(
                f"{prefix} framebuffer_hash: expected "
                f"{checkpoint.expected_framebuffer_hash!r}, actual "
                f"{actual.get('framebuffer_hash')!r}"
            )
        if (
            checkpoint.expected_sram_hash is not None
            and actual.get("sram_hash") != checkpoint.expected_sram_hash
        ):
            differences.append(
                f"{prefix} sram_hash: expected "
                f"{checkpoint.expected_sram_hash!r}, actual "
                f"{actual.get('sram_hash')!r}"
            )
        for probe_index, probe in enumerate(checkpoint.probes):
            if probe.expected is None:
                continue
            actual_value = actual["probes"][probe_index]["value"]
            if actual_value != probe.expected:
                differences.append(
                    f"{prefix} probe 0x{probe.address:08x}/{probe.size}: "
                    f"expected {probe.expected!r}, actual {actual_value!r}"
                )
    return differences


def validate_fingerprint(data: Any, source: str) -> dict[str, Any]:
    root = _expect_object(
        data, source, {"format_version", "scenario", "rom", "checkpoints"}
    )
    if (
        not _is_int(root["format_version"])
        or root["format_version"] != FINGERPRINT_FORMAT_VERSION
    ):
        raise PlaytestError(
            f"{source}.format_version must be integer {FINGERPRINT_FORMAT_VERSION}"
        )
    _expect_name(root["scenario"], f"{source}.scenario")
    rom = _expect_object(
        root["rom"], f"{source}.rom", {"sha1", "size", "title", "game_code"}
    )
    if not isinstance(rom["sha1"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", rom["sha1"]
    ):
        raise PlaytestError(f"{source}.rom.sha1 must be 40 lowercase hex digits")
    if not _is_int(rom["size"]) or rom["size"] <= 0:
        raise PlaytestError(f"{source}.rom.size must be a positive integer")
    for field, limit in (("title", 48), ("game_code", 16)):
        if not isinstance(rom[field], str) or len(rom[field]) > limit:
            raise PlaytestError(
                f"{source}.rom.{field} must be a string no longer than {limit} characters"
            )
    if not isinstance(root["checkpoints"], list):
        raise PlaytestError(f"{source}.checkpoints must be an array")
    previous_frame = -1
    names: set[str] = set()
    for index, raw in enumerate(root["checkpoints"]):
        path = f"{source}.checkpoints[{index}]"
        checkpoint = _expect_object(
            raw, path, {"frame", "name", "probes"}, {"framebuffer_hash", "sram_hash"}
        )
        frame = _expect_frame(checkpoint["frame"], f"{path}.frame")
        if frame <= previous_frame:
            raise PlaytestError(f"{path}.frame must be strictly increasing")
        previous_frame = frame
        name = _expect_name(checkpoint["name"], f"{path}.name")
        if name in names:
            raise PlaytestError(f"{path}.name duplicates {name!r}")
        names.add(name)
        framebuffer_hash = checkpoint.get("framebuffer_hash")
        if framebuffer_hash is not None and (
            not isinstance(framebuffer_hash, str) or not HASH_RE.fullmatch(framebuffer_hash)
        ):
            raise PlaytestError(f"{path}.framebuffer_hash is malformed")
        sram_hash = checkpoint.get("sram_hash")
        if sram_hash is not None and (
            not isinstance(sram_hash, str) or not SRAM_HASH_RE.fullmatch(sram_hash)
        ):
            raise PlaytestError(f"{path}.sram_hash is malformed")
        if not isinstance(checkpoint["probes"], list):
            raise PlaytestError(f"{path}.probes must be an array")
        previous_probe: tuple[int, int] | None = None
        for probe_index, raw_probe in enumerate(checkpoint["probes"]):
            probe_path = f"{path}.probes[{probe_index}]"
            probe = _expect_object(raw_probe, probe_path, {"address", "size", "value"})
            size = probe["size"]
            if not _is_int(size) or size not in (1, 2, 4):
                raise PlaytestError(f"{probe_path}.size must be integer 1, 2, or 4")
            address = _parse_address(probe["address"], size, f"{probe_path}.address")
            identity = (address, size)
            if previous_probe is not None and identity <= previous_probe:
                raise PlaytestError(f"{probe_path} must be sorted and unique by address/size")
            previous_probe = identity
            pattern = re.compile(rf"^0x[0-9a-f]{{{size * 2}}}$")
            if not isinstance(probe["value"], str) or not pattern.fullmatch(probe["value"]):
                raise PlaytestError(f"{probe_path}.value is malformed for size {size}")
    return root


def _recursive_differences(expected: Any, actual: Any, path: str = "") -> Iterable[str]:
    if type(expected) is not type(actual):
        yield f"{path or '<root>'}: expected type {type(expected).__name__}, actual {type(actual).__name__}"
        return
    if isinstance(expected, dict):
        for key in sorted(expected.keys() - actual.keys()):
            yield f"{path + '.' if path else ''}{key}: missing from actual capture"
        for key in sorted(actual.keys() - expected.keys()):
            yield f"{path + '.' if path else ''}{key}: unexpected in actual capture"
        for key in sorted(expected.keys() & actual.keys()):
            child = f"{path}.{key}" if path else key
            yield from _recursive_differences(expected[key], actual[key], child)
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            yield f"{path}: expected {len(expected)} item(s), actual {len(actual)}"
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            yield from _recursive_differences(
                expected_item, actual_item, f"{path}[{index}]"
            )
    elif expected != actual:
        yield f"{path}: expected {expected!r}, actual {actual!r}"


def compare_fingerprints(
    expected: dict[str, Any], actual: dict[str, Any], policy: str = "exact-rom"
) -> list[str]:
    if policy == "exact-rom":
        return list(_recursive_differences(expected, actual))
    if policy == "behavior":
        expected_behavior = {
            key: expected[key] for key in ("format_version", "scenario", "checkpoints")
        }
        actual_behavior = {
            key: actual[key] for key in ("format_version", "scenario", "checkpoints")
        }
        return list(_recursive_differences(expected_behavior, actual_behavior))
    raise ValueError(f"unknown verification policy: {policy}")


def format_rom_identity(provenance: dict[str, Any]) -> str:
    return (
        f"sha1={provenance['sha1']} size={provenance['size']} "
        f"title={provenance['title']!r} game_code={provenance['game_code']!r}"
    )


def _write_output(path: str, text: str) -> None:
    if path == "-":
        sys.stdout.write(text)
        return
    output = Path(path)
    try:
        output.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise PlaytestError(f"cannot write {output}: {exc}") from exc


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    capture_parser = subparsers.add_parser(
        "capture", help="run a scenario and emit its deterministic fingerprint"
    )
    capture_parser.add_argument("--rom", required=True, type=Path)
    capture_parser.add_argument("--scenario", required=True, type=Path)
    capture_parser.add_argument(
        "--sram-image",
        type=Path,
        default=None,
        help="optional exact 0x8000-byte raw SRAM image loaded before frame 0",
    )
    capture_parser.add_argument(
        "--output", "-o", default="-", help="output JSON path (default: stdout)"
    )
    capture_parser.add_argument(
        "--retries", type=int, default=0, metavar="N", help='bounded number of additional attempts (capped at MAX_RETRIES_CAP=5) after a libmGBA backend or compiler process time-out only -- never for a non-zero exit code or a mismatched/malformed-output diagnostic, which are deterministic and must never be silently retried. Default 0 (a single attempt, no retry). Every retried attempt is reported on stderr.'
    )

    verify_parser = subparsers.add_parser(
        "verify", help="capture and compare against an expected fingerprint"
    )
    verify_parser.add_argument("--rom", required=True, type=Path)
    verify_parser.add_argument("--scenario", required=True, type=Path)
    verify_parser.add_argument("--expected", required=True, type=Path)
    verify_parser.add_argument(
        "--sram-image",
        type=Path,
        default=None,
        help="optional exact 0x8000-byte raw SRAM image loaded before frame 0",
    )
    verify_parser.add_argument(
        "--policy",
        choices=("exact-rom", "behavior"),
        default="exact-rom",
        help=(
            "exact-rom (safe default) compares ROM identity and behavior; "
            "behavior explicitly compares checkpoints across different ROM identities"
        ),
    )
    verify_parser.add_argument(
        "--retries", type=int, default=0, metavar="N", help='bounded number of additional attempts (capped at MAX_RETRIES_CAP=5) after a libmGBA backend or compiler process time-out only -- never for a non-zero exit code or a mismatched/malformed-output diagnostic, which are deterministic and must never be silently retried. Default 0 (a single attempt, no retry). Every retried attempt is reported on stderr.'
    )

    backend_check_parser = subparsers.add_parser(
        "backend-check", help="compile the libmGBA backend without running a ROM"
    )
    backend_check_parser.add_argument(
        "--retries", type=int, default=0, metavar="N", help='bounded number of additional attempts (capped at MAX_RETRIES_CAP=5) after a libmGBA backend or compiler process time-out only -- never for a non-zero exit code or a mismatched/malformed-output diagnostic, which are deterministic and must never be silently retried. Default 0 (a single attempt, no retry). Every retried attempt is reported on stderr.'
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _make_parser().parse_args(argv)
    try:
        if args.retries < 0:
            raise PlaytestError(
                f"--retries must be a non-negative integer, got {args.retries}"
            )
        if args.mode == "backend-check":
            with tempfile.TemporaryDirectory(prefix="gba-playtest-check-") as temporary:
                build_backend(Path(temporary) / "gba-playtest-backend", args.retries)
            print("libmGBA backend: available")
            return 0
        scenario = load_scenario(args.scenario)
        actual = capture(args.rom, scenario, args.sram_image, args.retries)
        if args.mode == "capture":
            _write_output(args.output, serialize_fingerprint(actual))
            return 0
        expected = validate_fingerprint(_read_json(args.expected), str(args.expected))
        differences = compare_fingerprints(expected, actual, args.policy)
        if differences:
            print(
                f"fingerprint mismatch for scenario {scenario.name!r} "
                f"under policy {args.policy!r}:",
                file=sys.stderr,
            )
            print(
                f"  baseline ROM: {format_rom_identity(expected['rom'])}",
                file=sys.stderr,
            )
            print(
                f"  candidate ROM: {format_rom_identity(actual['rom'])}",
                file=sys.stderr,
            )
            for difference in differences:
                print(f"  - {difference}", file=sys.stderr)
            return 1
        print(
            f"fingerprint verified: policy={args.policy} scenario={scenario.name} "
            f"checkpoints={len(scenario.checkpoints)}\n"
            f"  baseline ROM: {format_rom_identity(expected['rom'])}\n"
            f"  candidate ROM: {format_rom_identity(actual['rom'])}"
        )
        return 0
    except PlaytestError as exc:
        print(f"gba-playtest: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
