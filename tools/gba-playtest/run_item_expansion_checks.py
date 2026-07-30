#!/usr/bin/env python3
"""Runtime item-ID-expansion check orchestrator (issue #10).

Invoked by `modern.mk`'s `expansion-modern-itemexpansion-check` target, once
per MODERN_CONFIG, against a ROM built with `FE8_ITEM_ID_CAP=0xCE
FE8_EXPANSION_ITEMTEST=1`. It:

1. Resolves `gItemExpansionProbe`'s live EWRAM address from the *linked
   ELF's own symbol table* (never a hardcoded address and never a committed
   frame/framebuffer oracle), so the same check works for debug and release
   and survives any legitimate layout change an expanded ID space causes.
2. Renders the scenario (input script + probe list) into the caller-supplied
   build directory and runs it through tools/gba-playtest/gba_playtest.py.
3. Asserts every recorded value produced by the ROM's own production paths:
   the runtime `GetItemData()` record, the event engine's `EV_CMD_GIVEITEM`
   decoder placing the expanded ID into a real unit inventory, the item
   menu/stat-screen UI draw, and the MultiArena/link, game-save and
   suspend-save/resume roundtrips -- plus the unchanged legacy 0xCD and
   empty (0x0000) slots next to them.

Every failure names the field, the expected value and the observed value.
Stdlib only, matching this repository's conventions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
GBA_PLAYTEST = PLAYTEST_DIR / "gba_playtest.py"

PROBE_SYMBOL = "gItemExpansionProbe"
PROBE_MAGIC = 0x49584345  # ASCII "IXCE", include/expansion_itemtest.h

# Field order MUST match struct ItemExpansionProbe in
# include/expansion_itemtest.h (all u32, so index i lives at base + 4 * i).
PROBE_FIELDS = (
    "magic",
    "stagesCompleted",
    "configuredCap",
    "dataNumber",
    "dataNameTextId",
    "dataDescTextId",
    "dataIconId",
    "dataWeaponType",
    "dataMaxUses",
    "dataAttributes",
    "madeItem",
    "lookupIndex",
    "lookupUses",
    "legacyDataNumber",
    "eventUnitPid",
    "eventItemSlot",
    "eventItem",
    "eventLegacyItem",
    "uiNamePtr",
    "uiIconId",
    "uiMenuIconTile",
    "uiMenuUsesTile",
    "uiMenuNameTile",
    "uiStatIconTile",
    "uiStatSlashTile",
    "uiDescId",
    "arenaItem",
    "arenaLegacyItem",
    "arenaEmptySlot",
    "gameSaveItem",
    "gameSaveLegacyItem",
    "gameSaveEmptySlot",
    "suspendItem",
    "suspendLegacyItem",
    "suspendEmptySlot",
    "bootPrepared",
    "phaseWaitFrames",
    "phaseTimedOut",
    "eventWaitFrames",
    "lastChapterIndex",
    "lastFaction",
    "mapMainSeen",
    "playerPhaseSeen",
    "procStateBits",
    "procStateNow",
    "wmLocation",
    "wmCurrentNode",
    "gameSavePackedField",
    "suspendPackedField",
)

ALL_STAGES = 0x3F  # ITEMTEST_STAGE_ALL, include/expansion_itemtest.h
STAGE_ITEMDATA = 0x01  # ITEMTEST_STAGE_ITEMDATA

# Deterministic intro skip: the same spaced A/START taps the existing
# debugtools-hub scenarios use to walk the pre-title sequence. No hotkey and
# no menu input at all -- the probe build's own Title_IDLE hook performs the
# ordinary "start the game" transition itself, in debug and release alike.
# Deterministic, input-scripted boot to the real Chapter 2 map: the same
# spaced A/START taps the committed debugtools-hub/savesuspend scenarios use
# to walk the pre-title sequence, the world map and the scripted opening
# dialogue. No debug hotkey and no menu navigation is involved -- the probe
# build's own Title_IDLE hook performs the ordinary "start the game"
# transition itself, so the identical script drives a debug and a release
# ROM. Input stops once the map is interactive; the in-ROM probe then waits
# out its own settle window before touching anything.
# Pre-title sequence: the same alternating A/START taps the committed
# debugtools-hub scenarios use to walk the intro to the title screen.
BOOT_INTRO_FRAMES = [
    {"start": 90, "end": 95, "keys": ["A"]},
    {"start": 150, "end": 155, "keys": ["START"]},
    {"start": 210, "end": 215, "keys": ["A"]},
    {"start": 270, "end": 275, "keys": ["START"]},
    {"start": 330, "end": 335, "keys": ["A"]},
    {"start": 390, "end": 395, "keys": ["START"]},
    {"start": 450, "end": 455, "keys": ["A"]},
]

# Scripted chapter-opening dialogue: spaced A taps, the same way the
# committed debugtools/savesuspend scenarios advance it, and the same way a
# player dismisses the production "got item" popup the probe's own GIVEITEM
# event raises later. The probe build commits its own boot from a settled
# title screen shortly before the first tap below (straight to the battle
# map -- there is no world-map navigation to script), so no tap can race
# the title transition.
BOOT_TAP_FIRST_FRAME = 750
BOOT_TAP_LAST_FRAME = 14650
BOOT_TAP_PERIOD = 30
BOOT_WORLDMAP_JUMP_FRAMES = tuple(range(1500, 9001, 300))


def boot_frames() -> list[dict]:
    frames = list(BOOT_INTRO_FRAMES)
    frames.extend(
        {"start": frame, "end": frame + 6, "keys": ["L"]}
        for frame in BOOT_WORLDMAP_JUMP_FRAMES
    )
    frames.extend(
        {"start": frame, "end": frame + 4, "keys": ["A"]}
        for frame in range(BOOT_TAP_FIRST_FRAME, BOOT_TAP_LAST_FRAME + 1, BOOT_TAP_PERIOD)
        if not any(jump <= frame <= jump + 6 for jump in BOOT_WORLDMAP_JUMP_FRAMES)
    )
    frames.sort(key=lambda entry: entry["start"])
    return frames


DEFAULT_FRAME = 22000


class CheckError(Exception):
    pass


def resolve_symbol(elf: Path, symbol: str) -> tuple[int, int]:
    nm = os.environ.get("NM", "arm-none-eabi-nm")
    try:
        output = subprocess.run(
            [nm, "-S", str(elf)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        ).stdout
    except FileNotFoundError as exc:
        raise CheckError(f"cannot run {nm!r} to resolve {symbol} in {elf}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise CheckError(f"{nm} failed on {elf}: {exc.stderr.strip()}") from exc
    pattern = re.compile(r"^([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+\S\s+" + re.escape(symbol) + r"$")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match:
            return int(match.group(1), 16), int(match.group(2), 16)
    raise CheckError(
        f"{symbol} not found in {elf}: build the ROM with "
        f"FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1"
    )


def build_scenario(base: int, frame: int) -> dict:
    probes = [
        {"address": f"0x{base + 4 * index:08x}", "size": 4}
        for index in range(len(PROBE_FIELDS))
    ]
    return {
        "schema_version": 1,
        "name": "itemexpansion-runtime",
        "description": (
            "Issue #10 runtime item-ID-expansion probe. Boots the probe ROM to "
            "the real Chapter 2 map with no menu input, then reads back what the "
            "ROM's own production paths recorded in gItemExpansionProbe: "
            "GetItemData(0xCE), the event engine's EV_CMD_GIVEITEM decoder, the "
            "item menu/stat-screen draw, and the MultiArena/link, game-save and "
            "suspend-save/resume roundtrips. Probe addresses are resolved from "
            "the linked ELF, so no ROM layout is pinned and no committed "
            "framebuffer oracle is involved."
        ),
        "frames": boot_frames(),
        "checkpoints": [
            {
                "name": "itemexpansion-probe-complete",
                "frame": frame,
                "framebuffer": False,
                "probes": probes,
            }
        ],
    }


def capture(rom: Path, scenario_path: Path, output_path: Path) -> dict:
    command = [
        sys.executable,
        str(GBA_PLAYTEST),
        "capture",
        "--rom",
        str(rom),
        "--scenario",
        str(scenario_path),
        "--output",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    if completed.returncode != 0:
        raise CheckError(
            "gba_playtest capture failed "
            f"(exit {completed.returncode}):\n{completed.stdout}{completed.stderr}"
        )
    return json.loads(output_path.read_text(encoding="utf-8"))


def read_values(fingerprint: dict) -> dict[str, int]:
    checkpoint = fingerprint["checkpoints"][0]
    probes = checkpoint["probes"]
    if len(probes) != len(PROBE_FIELDS):
        raise CheckError(
            f"captured {len(probes)} probes, expected {len(PROBE_FIELDS)}"
        )
    return {
        name: int(probe["value"], 16) for name, probe in zip(PROBE_FIELDS, probes)
    }


def check(values: dict[str, int], cap: int, require: str) -> list[str]:
    """Assert the ROM-recorded production results. Every expectation below
    is a property of the item ID space itself, never a copy of a
    framebuffer/ROM-layout oracle.

    ``require="all"`` demands every stage, including the ones that need a
    live battle map (event decoder, item UI, save/suspend/arena
    roundtrips). ``require="boot"`` demands only the stages a ROM records
    before any map exists -- the runtime item record itself -- and is used
    for the modern release configuration, whose battle map is unreachable
    in this harness for reasons that have nothing to do with the item ID
    space (see docs/id_space.md, "Release-configuration limitation")."""
    failures: list[str] = []
    expansion_id = 0xCE
    legacy_id = 0xCD

    def expect(field: str, expected: int, why: str) -> None:
        actual = values[field]
        if actual != expected:
            failures.append(
                f"{field}: expected 0x{expected:x} ({why}), observed 0x{actual:x}"
            )

    def expect_nonzero(field: str, why: str) -> None:
        if values[field] == 0:
            failures.append(f"{field}: expected a non-zero value ({why}), observed 0")

    # Harness liveness first: a partial or hung run must never look like a pass.
    expect("configuredCap", cap, "ITEM_ID_CONFIGURED_CAP compiled into the ROM")
    expect("bootPrepared", 1, "the probe ROM started the game by itself")
    if not values["stagesCompleted"] & STAGE_ITEMDATA:
        failures.append(
            "stagesCompleted: the runtime item-record stage never ran, observed "
            f"0x{values['stagesCompleted']:x}"
        )
    if require == "all":
        expect("magic", PROBE_MAGIC, "every probe stage ran to completion")
        expect("stagesCompleted", ALL_STAGES, "all six production stages recorded")
        expect("phaseTimedOut", 0, "a real Player Phase was reached, not the fail-safe")

    # Stage 1 -- runtime GetItemData() record for the expanded ID.
    expect("dataNumber", expansion_id, "GetItemData(0xCE)->number")
    expect("dataWeaponType", 0x09, "ITYPE_ITEM, as authored in items_expansion.json")
    expect("dataMaxUses", 1, "maxUses, as authored in items_expansion.json")
    expect("dataNameTextId", 0, "reserved blank slot authors no new text asset")
    expect("dataIconId", 0, "iconId, as authored in items_expansion.json")
    expect("madeItem", 0x01CE, "MakeNewItem(0xCE) = uses<<8 | id")
    expect("lookupIndex", expansion_id, "GetItemIndex() of the made item")
    expect("lookupUses", 1, "GetItemUses() of the made item")
    expect("legacyDataNumber", legacy_id, "GetItemData(0xCD)->number is untouched")

    if require != "all":
        return failures

    # Stage 2 -- production event decoder wrote a real unit inventory.
    expect("eventUnitPid", 0x01, "CHARACTER_EIRIKA, the event's target unit")
    expect("eventItem", 0x01CE, "expanded item halfword in the unit's inventory")
    expect("eventLegacyItem", 0x00CD, "legacy 0xCD item given by the same command")
    if values["eventItemSlot"] > 4:
        failures.append(
            f"eventItemSlot: expected a real inventory slot 0..4, observed "
            f"0x{values['eventItemSlot']:x}"
        )

    # Stage 3 -- production item UI lookup/draw for the expanded ID.
    expect("uiIconId", 0, "GetItemIconId() as the UI itself read it")
    expect("uiDescId", 0, "GetItemDescId() for the reserved blank slot")
    # GetItemName() resolves the record's nameTextId through the text
    # system, which hands back a decoded string in EWRAM (not a raw ROM
    # pointer), so accept either -- what matters is that the expanded ID
    # resolved to a real string the UI could draw, not where it lives.
    if not (
        0x02000000 <= values["uiNamePtr"] < 0x02040000
        or 0x08000000 <= values["uiNamePtr"] < 0x0A000000
    ):
        failures.append(
            "uiNamePtr: expected GetItemName(0xCE) to resolve to a real string "
            f"(EWRAM or ROM), observed 0x{values['uiNamePtr']:x}"
        )
    if values["uiMenuIconTile"] != values["uiStatIconTile"]:
        failures.append(
            "uiMenuIconTile/uiStatIconTile: both production draw paths must place "
            f"the same icon for 0xCE, observed 0x{values['uiMenuIconTile']:x} vs "
            f"0x{values['uiStatIconTile']:x}"
        )
    expect_nonzero("uiMenuIconTile", "DrawIcon() wrote the item menu line's icon tile")
    expect_nonzero("uiMenuUsesTile", "the item menu line's uses digit was drawn")
    expect_nonzero("uiMenuNameTile", "PutText() wrote the item menu line's name tiles")
    expect_nonzero("uiStatIconTile", "the stat-screen item line drew its icon")
    expect_nonzero("uiStatSlashTile", "the stat-screen item line drew its uses separator")

    # Stages 4-6 -- persisted/link representations, bit-exact.
    for field, why in (
        ("arenaItem", "MultiArena/link team roundtrip"),
        ("gameSaveItem", "game-save pack/unpack roundtrip"),
        ("suspendItem", "suspend-save encode/decode roundtrip"),
        ("gameSavePackedField", "packed 14-bit game-save item field"),
        ("suspendPackedField", "packed suspend-save item field"),
    ):
        expect(field, 0x01CE, f"expanded item survives the {why} bit-exact")
    for field, why in (
        ("arenaLegacyItem", "MultiArena/link team roundtrip"),
        ("gameSaveLegacyItem", "game-save pack/unpack roundtrip"),
        ("suspendLegacyItem", "suspend-save encode/decode roundtrip"),
    ):
        expect(field, 0x00CD, f"legacy 0xCD item is unchanged by the {why}")
    for field, why in (
        ("arenaEmptySlot", "MultiArena/link team roundtrip"),
        ("gameSaveEmptySlot", "game-save pack/unpack roundtrip"),
        ("suspendEmptySlot", "suspend-save encode/decode roundtrip"),
    ):
        expect(field, 0x0000, f"an empty inventory slot stays ITEM_NONE across the {why}")

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--cap", default="0xCE")
    parser.add_argument("--frame", type=int, default=DEFAULT_FRAME)
    parser.add_argument(
        "--require-stages",
        choices=("all", "boot"),
        default="all",
        help=(
            "all (default) requires every production stage; boot requires only "
            "the stages a ROM records before a battle map exists"
        ),
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="print every observed probe value and skip the assertions",
    )
    args = parser.parse_args(argv)

    try:
        cap = int(args.cap, 0)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        base, size = resolve_symbol(args.elf, PROBE_SYMBOL)
        if size < 4 * len(PROBE_FIELDS):
            raise CheckError(
                f"{PROBE_SYMBOL} is {size} bytes in {args.elf}, expected at least "
                f"{4 * len(PROBE_FIELDS)}: struct ItemExpansionProbe and PROBE_FIELDS "
                f"are out of sync"
            )
        scenario = build_scenario(base, args.frame)
        scenario_path = args.out_dir / f"itemexpansion-runtime-modern-{args.config}.json"
        scenario_path.write_text(
            json.dumps(scenario, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        fingerprint_path = args.out_dir / f"itemexpansion-runtime-modern-{args.config}.captured.json"
        fingerprint = capture(args.rom, scenario_path, fingerprint_path)
        values = read_values(fingerprint)

        print(
            f"item-expansion runtime probe: rom={args.rom} config={args.config} "
            f"{PROBE_SYMBOL}=0x{base:08x} frame={args.frame}"
        )
        for name in PROBE_FIELDS:
            print(f"  {name} = 0x{values[name]:08x}")

        if args.report_only:
            return 0

        failures = check(values, cap, args.require_stages)
        if failures:
            print(
                f"item-expansion runtime probe FAILED (config={args.config}):",
                file=sys.stderr,
            )
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1

        if args.require_stages == "all":
            print(
                f"item-expansion runtime probe passed (config={args.config}): "
                f"runtime item record, event GIVEITEM decoder, item UI draw, "
                f"MultiArena/link, and the game-save/suspend pack+unpack all carry 0xCE "
                f"bit-exact, with 0x00CD and 0x0000 unchanged"
            )
        else:
            print(
                f"item-expansion runtime probe passed (config={args.config}, "
                f"require-stages=boot): the running ROM's own GetItemData/"
                f"MakeNewItem/GetItemIndex/GetItemUses resolve 0xCE to the "
                f"expanded record, with 0xCD unchanged; stages needing a live "
                f"battle map are covered by the debug configuration (see "
                f"docs/id_space.md)"
            )
        return 0
    except CheckError as exc:
        print(f"run_item_expansion_checks: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
