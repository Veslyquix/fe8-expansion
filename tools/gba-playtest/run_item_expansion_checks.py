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
4. With `--content 1` (issue #6), additionally asserts the bundled
   content example: the compile-time content flag, the bundled item's
   typed ID, the ORIGINAL authored display name the production
   `GetItemName()` returned (length + FNV-1a 32, recomputed here from
   the authored name), the public mechanics registry's contents after
   the framework's single built-in install point ran, and -- on a live map --
   the content mechanic's bounded bonus firing for the item's bearer and NOT
   firing for a deployed control unit that does not carry it.

Every expected item-record value is READ FROM THE AUTHORED SOURCE OF TRUTH
(the `ITEM_EXPANSION_CE` record in `src/data_items.c`, its display name in
`src/data/items_expansion_content_text.h`, plus the `ITYPE_*`/`IA_*`/
`CHARACTER_*` headers and the content module's own bonus constants), never
restated as a literal here: the check therefore fails if the ROM and the
authored data ever disagree, and cannot silently drift when the record is
re-authored.

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
    "contentEnabled",
    "contentItemId",
    "contentMechanicsCount",
    "contentMechanicIndex",
    "contentSampleIndex",
    "contentRegisterOk",
    "contentRegisterErr",
    "contentLastResult",
    "contentBearerPid",
    "contentBearerItemSlot",
    "contentBearerAvoidDelta",
    "contentBearerDefenseDelta",
    "contentControlPid",
    "contentControlItemSlot",
    "contentControlAvoidDelta",
    "contentControlDefenseDelta",
    "contentApplyCount",
    "contentSampleTriggerCount",
    "uiNameLen",
    "uiNameHash",
)

ALL_STAGES = 0x7F  # ITEMTEST_STAGE_ALL, include/expansion_itemtest.h
STAGE_ITEMDATA = 0x01  # ITEMTEST_STAGE_ITEMDATA
STAGE_CONTENT = 0x40  # ITEMTEST_STAGE_CONTENT
INDEX_NONE = 0xFFFFFFFF  # ITEMTEST_INDEX_NONE

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


def fnv1a32(data: bytes) -> int:
    """FNV-1a 32 -- the same constants src/expansion_itemtest.c uses."""
    digest = 2166136261
    for byte in data:
        digest = ((digest ^ byte) * 16777619) & 0xFFFFFFFF
    return digest


_ENUM_ENTRY_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?0[xX][0-9A-Fa-f]+|-?\d+)\s*,?\s*(//.*)?$"
)
_SHIFT_ENTRY_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(1\s*<<\s*(\d+)\)\s*,?\s*(//.*)?$"
)
_DEFINE_ENTRY_RE = re.compile(
    r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(-?0[xX][0-9A-Fa-f]+|-?\d+)\s*(?:/\*.*?\*/|//.*)?\s*$"
)


def extract_enum_constants(header_path, name_prefix=None):
    """Scan a C header for ``NAME = <value>,`` enum entries (plain integer
    literals) and ``NAME = (1 << N),`` shift-style bitmask entries.

    Returns an ordered ``dict`` of ``name -> value``. Intentionally simple
    (regex, not a real C parser) -- sufficient for this project's
    enum-style constant headers.
    """
    constants = {}
    with open(header_path, "r", encoding="utf-8") as handle:
        for line in handle:
            match = _ENUM_ENTRY_RE.match(line)
            if match:
                name = match.group(1)
                if name_prefix is not None and not name.startswith(name_prefix):
                    continue
                value_text = match.group(2)
                constants[name] = (
                    int(value_text, 16) if value_text.lower().startswith(("0x", "-0x"))
                    else int(value_text)
                )
                continue
            match = _SHIFT_ENTRY_RE.match(line)
            if match:
                name = match.group(1)
                if name_prefix is not None and not name.startswith(name_prefix):
                    continue
                constants[name] = 1 << int(match.group(2))
    return constants


def extract_define_constant(header_path, name):
    """Scan a C header for a single ``#define NAME VALUE`` object-like macro."""
    with open(header_path, "r", encoding="utf-8") as handle:
        for line in handle:
            match = _DEFINE_ENTRY_RE.match(line)
            if not match or match.group(1) != name:
                continue
            value_text = match.group(2)
            return int(value_text, 16) if value_text.lower().startswith(("0x", "-0x")) else int(value_text)
    raise CheckError(f"could not find '#define {name} ...' in {header_path}")


class AuthoredRecord:
    """Every expected value of the issue #6 authored expansion item record,
    resolved from the repository's own hand-authored sources: the
    ITEM_EXPANSION_CE record in src/data_items.c (the actual compiled
    table -- the single source of truth, not a parallel copy of it) and
    its display name in src/data/items_expansion_content_text.h."""

    def __init__(self, cap: int):
        expansion_header = REPO_ROOT / "include" / "constants" / "items_expansion.h"
        bmitem_header = REPO_ROOT / "include" / "bmitem.h"
        data_items_c = REPO_ROOT / "src" / "data_items.c"
        content_text_h = REPO_ROOT / "src" / "data" / "items_expansion_content_text.h"

        expansion_enum = extract_enum_constants(str(expansion_header), name_prefix="ITEM_")
        if "ITEM_EXPANSION_CE" not in expansion_enum:
            raise CheckError(f"ITEM_EXPANSION_CE not found in {expansion_header}")
        item_id = expansion_enum["ITEM_EXPANSION_CE"]

        source = data_items_c.read_text(encoding="utf-8")
        block_match = re.search(
            r"\[ITEM_EXPANSION_CE\]\s*=\s*\{(.*?)\n\t\},", source, re.S)
        if not block_match:
            raise CheckError(f"could not find the ITEM_EXPANSION_CE record in {data_items_c}")
        block = block_match.group(1)

        def field(name, default=None):
            m = re.search(r"\." + name + r"\s*=\s*([^,]+),", block)
            if not m:
                if default is not None:
                    return default
                raise CheckError(f"ITEM_EXPANSION_CE record has no .{name} field in {data_items_c}")
            return m.group(1).strip()

        weapon_types = extract_enum_constants(str(bmitem_header), name_prefix="ITYPE_")
        attribute_flags = extract_enum_constants(str(bmitem_header), name_prefix="IA_")

        weapon_type_name = field("weaponType")
        if weapon_type_name not in weapon_types:
            raise CheckError(f"unknown weaponType '{weapon_type_name}' (not in {bmitem_header})")

        attributes_value = 0
        for name in field("attributes", default="0").split("|"):
            name = name.strip()
            if name == "0":
                continue
            if name not in attribute_flags:
                raise CheckError(f"unknown attribute '{name}' (not in {bmitem_header})")
            attributes_value |= attribute_flags[name]

        content_source = content_text_h.read_text(encoding="utf-8")
        name_match = re.search(
            r"\{\s*ITEM_EXPANSION_CE\s*,\s*\"([^\"]*)\"\s*\}", content_source)
        if not name_match:
            raise CheckError(
                f"could not find the ITEM_EXPANSION_CE display name in {content_text_h}")
        authoring_name = name_match.group(1)

        self.item_name = "ITEM_EXPANSION_CE"
        self.item_id = item_id
        self.name_text_id = 0
        self.desc_text_id = 0
        self.use_desc_text_id = 0
        self.weapon_type = weapon_types[weapon_type_name]
        self.weapon_type_name = weapon_type_name
        self.attributes = attributes_value
        self.max_uses = int(field("maxUses"), 0)
        self.icon_id = int(field("iconId"), 0)
        # MakeNewItem(item) packs uses into the high byte (see src/bmitem.c).
        self.made_item = (self.max_uses << 8) | self.item_id
        # Issue #6: the ORIGINAL display name, authored literally in
        # src/data/items_expansion_content_text.h. The ROM records the
        # length and FNV-1a 32 hash of whatever the production
        # GetItemName() returned, so recomputing both here binds the drawn
        # text to the authored source of truth with no oracle file.
        self.authoring_name = authoring_name
        self.name_len = len(authoring_name)
        self.name_hash = fnv1a32(authoring_name.encode("ascii"))


class ContentContract:
    """The issue #6 content module's own public constants and the two units
    the runtime stage uses, read from their defining headers."""

    def __init__(self):
        content_header = REPO_ROOT / "include" / "expansion_starter_content.h"
        mechanics_header = REPO_ROOT / "include" / "expansion_mechanics.h"
        characters_header = REPO_ROOT / "include" / "constants" / "characters.h"
        itemtest_source = REPO_ROOT / "src" / "expansion_itemtest.c"

        self.avoid_bonus = extract_define_constant(
            str(content_header), "EXPANSION_STARTER_CONTENT_AVOID_BONUS")
        self.avoid_cap = extract_define_constant(
            str(content_header), "EXPANSION_STARTER_CONTENT_AVOID_CAP")
        self.defense_bonus = extract_define_constant(
            str(mechanics_header), "EXPANSION_MECHANICS_SAMPLE_GUARD_BONUS")

        characters = extract_enum_constants(
            str(characters_header), name_prefix="CHARACTER_")
        source = itemtest_source.read_text(encoding="utf-8")
        self.bearer_pid = characters[_defined_symbol(source, "ITEMTEST_TARGET_PID")]
        self.control_pid = characters[_defined_symbol(source, "ITEMTEST_CONTROL_PID")]


def _defined_symbol(source: str, macro: str) -> str:
    match = re.search(r"^#define\s+" + re.escape(macro) + r"\s+(\w+)\s*$", source, re.M)
    if not match:
        raise CheckError(f"cannot find '#define {macro} ...' in src/expansion_itemtest.c")
    return match.group(1)


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


def check(values: dict[str, int], cap: int, require: str,
          authored: "AuthoredRecord", content: int,
          contract: "ContentContract | None" = None) -> list[str]:
    """Assert the ROM-recorded production results. Every expectation below
    is a property of the item ID space itself or of the authored record and
    the content module's own public constants -- never a copy of a
    framebuffer/ROM-layout oracle.

    ``require="all"`` demands every stage, including the ones that need a
    live battle map (event decoder, item UI, save/suspend/arena
    roundtrips, issue #6 content mechanic). ``require="boot"`` demands only
    the stages a ROM records before any map exists -- the runtime item
    record itself and the issue #6 content config/registry state -- and is
    used for the modern release configuration, whose battle map is
    unreachable in this harness for reasons that have nothing to do with the
    item ID space (see docs/id_space.md, "Release-configuration
    limitation")."""
    failures: list[str] = []
    expansion_id = authored.item_id
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
        expect("stagesCompleted", ALL_STAGES, "all seven production stages recorded")
        expect("phaseTimedOut", 0, "a real Player Phase was reached, not the fail-safe")

    # Stage 1 -- runtime GetItemData() record for the expanded ID, compared
    # field-for-field against the authored ITEM_EXPANSION_CE record in
    # src/data_items.c.
    expect("dataNumber", expansion_id, f"GetItemData(0x{expansion_id:X})->number")
    expect("dataWeaponType", authored.weapon_type,
           f"{authored.weapon_type_name}, as authored in src/data_items.c")
    expect("dataMaxUses", authored.max_uses, "maxUses, as authored in src/data_items.c")
    expect("dataNameTextId", authored.name_text_id,
           "nameTextId stays 0: an authored content record consumes no slot in "
           "the shared, Huffman-compressed global message table")
    expect("dataDescTextId", authored.desc_text_id,
           "descTextId stays 0 for the same reason (see docs/starter_features.md, "
           "\"Config-gated content text\")")
    expect("dataIconId", authored.icon_id, "iconId, as authored in src/data_items.c")
    expect("dataAttributes", authored.attributes,
           "attributes bitmask, as authored in src/data_items.c")
    expect("madeItem", authored.made_item,
           f"MakeNewItem(0x{expansion_id:X}) = authored uses<<8 | id")
    expect("lookupIndex", expansion_id, "GetItemIndex() of the made item")
    expect("lookupUses", authored.max_uses, "GetItemUses() of the made item")
    expect("legacyDataNumber", legacy_id, "GetItemData(0xCD)->number is untouched")

    # Issue #6 content example, boot half: config flag + public registry
    # state. Recorded before any map exists, so a release ROM proves it too.
    if content:
        expect("contentEnabled", 1,
               "FE8_EXPANSION_STARTER_CONTENT compiled into the ROM")
        expect("contentItemId", expansion_id,
               "ExpansionStarterContentItemId(), the typed bundled item ID")
        expect("contentMechanicsCount", 2,
               "the content-free sample plus the bundled content mechanic")
        expect("contentRegisterOk", 2, "both registered through the public API")
        expect("contentRegisterErr", 0, "no rejected registration")
        expect("contentLastResult", 0, "EXPANSION_MECHANICS_OK")
        if values["contentMechanicIndex"] == INDEX_NONE:
            failures.append(
                "contentMechanicIndex: the bundled content mechanic is not in the "
                "public registry")
        if values["contentSampleIndex"] == INDEX_NONE:
            failures.append(
                "contentSampleIndex: the content-free sample mechanic is not in the "
                "public registry")
    else:
        expect("contentEnabled", 0, "the content flag is off in this build")
        expect("contentItemId", 0,
               "ITEM_ID_SENTINEL: the disabled content stub exposes no item")

    if require != "all":
        return failures

    # Stage 2 -- production event decoder wrote a real unit inventory.
    expect("eventUnitPid", 0x01, "CHARACTER_EIRIKA, the event's target unit")
    expect("eventItem", authored.made_item,
           "expanded item halfword in the unit's inventory")
    expect("eventLegacyItem", 0x00CD, "legacy 0xCD item given by the same command")
    if values["eventItemSlot"] > 4:
        failures.append(
            f"eventItemSlot: expected a real inventory slot 0..4, observed "
            f"0x{values['eventItemSlot']:x}"
        )

    # Stage 3 -- production item UI lookup/draw for the expanded ID.
    expect("uiIconId", authored.icon_id, "GetItemIconId() as the UI itself read it")
    expect("uiDescId", authored.desc_text_id,
           f"GetItemDescId(0x{expansion_id:X}) reads the record's own (unbound) "
           "description slot -- the help box shows no borrowed vanilla text")
    # GetItemName() resolves the record's nameTextId through the text
    # system, which hands back a decoded string in EWRAM (not a raw ROM
    # pointer), so accept either -- what matters is that the expanded ID
    # resolved to a real string the UI could draw, not where it lives.
    if not (
        0x02000000 <= values["uiNamePtr"] < 0x02040000
        or 0x08000000 <= values["uiNamePtr"] < 0x0A000000
    ):
        failures.append(
            f"uiNamePtr: expected GetItemName(0x{expansion_id:X}) to resolve to a "
            f"real string (EWRAM or ROM), observed 0x{values['uiNamePtr']:x}"
        )
    if content:
        # The production name path returned the ORIGINAL authored text --
        # byte for byte, as scalars. This is what proves the content example
        # kept real authored content after the shared message table was
        # (correctly) left alone: the string comes from the build-local
        # generated content text table, through the narrow typed accessor
        # ExpansionStarterContentItemName(), read by the unmodified
        # GetItemName() every item menu / trade / shop / stat screen uses.
        expect("uiNameLen", authored.name_len,
               f"length of the authored name {authored.authoring_name!r}")
        expect("uiNameHash", authored.name_hash,
               f"FNV-1a 32 of the authored name {authored.authoring_name!r} "
               "as GetItemName() returned it")

    if values["uiMenuIconTile"] != values["uiStatIconTile"]:
        failures.append(
            "uiMenuIconTile/uiStatIconTile: both production draw paths must place "
            f"the same icon for 0x{expansion_id:X}, observed "
            f"0x{values['uiMenuIconTile']:x} vs 0x{values['uiStatIconTile']:x}"
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
        expect(field, authored.made_item,
               f"expanded item survives the {why} bit-exact")
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

    # Stage 7 (issue #6) -- the bundled content mechanic on a live map, with
    # its own in-run negative control.
    if content and contract is not None:
        expect("contentBearerPid", contract.bearer_pid,
               "the deployed unit the production event gave the content item to")
        expect("contentControlPid", contract.control_pid,
               "the deployed control unit that never received it")
        if values["contentBearerItemSlot"] > 4:
            failures.append(
                "contentBearerItemSlot: expected the bearer to carry the content "
                f"item in a real slot 0..4, observed "
                f"0x{values['contentBearerItemSlot']:x}")
        expect("contentControlItemSlot", INDEX_NONE,
               "the control unit does not carry the content item")
        expect("contentBearerAvoidDelta", contract.avoid_bonus,
               "the content mechanic's bounded avoid bonus, for the bearer")
        expect("contentControlAvoidDelta", 0,
               "the content mechanic does NOT fire for a unit without the item")
        expect("contentBearerDefenseDelta", contract.defense_bonus,
               "the content-free sample still grants its own bounded bonus")
        expect("contentControlDefenseDelta", contract.defense_bonus,
               "the content-free sample is unaffected by the content item")
        expect("contentApplyCount", 2, "one public seam apply per combatant")
        expect("contentSampleTriggerCount", 2,
               "the content-free sample fired for both full-HP combatants")
    elif not content:
        expect("contentBearerItemSlot", INDEX_NONE,
               "no content bearer exists when the content flag is off")
        expect("contentControlItemSlot", INDEX_NONE,
               "no content control exists when the content flag is off")
        for field in ("contentBearerAvoidDelta", "contentBearerDefenseDelta",
                      "contentControlAvoidDelta", "contentControlDefenseDelta",
                      "contentApplyCount", "contentSampleTriggerCount"):
            expect(field, 0, "the content stage applies nothing when the flag is off")

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
        "--content",
        default="0",
        help=(
            "1 when the ROM was built with EXPANSION_STARTER_CONTENT=1 (issue "
            "#6 bundled content example, which also requires "
            "EXPANSION_MECHANICS_HOOKS=1 EXPANSION_MECHANICS_SAMPLE=1); the "
            "content assertions become negative controls at 0"
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
        content = int(args.content or "0", 0)
        if content not in (0, 1):
            raise CheckError(f"--content must be 0 or 1, got {args.content!r}")
        authored = AuthoredRecord(cap)
        contract = ContentContract() if content else None
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
            f"{PROBE_SYMBOL}=0x{base:08x} frame={args.frame} content={content}"
        )
        print(
            f"  authored record: {authored.item_name}=0x{authored.item_id:02X} "
            f"type={authored.weapon_type_name} uses={authored.max_uses} "
            f"icon={authored.icon_id} attrs=0x{authored.attributes:X} "
            f"name/desc/useDesc={authored.name_text_id}/{authored.desc_text_id}/"
            f"{authored.use_desc_text_id}"
        )
        print(
            f"  authored content text: name={authored.authoring_name!r} "
            f"len={authored.name_len} fnv1a32=0x{authored.name_hash:08x} "
            "(no shared message consumed)"
        )
        for name in PROBE_FIELDS:
            print(f"  {name} = 0x{values[name]:08x}")

        if args.report_only:
            return 0

        failures = check(values, cap, args.require_stages, authored, content, contract)

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
                f"MultiArena/link, and the game-save/suspend pack+unpack all carry "
                f"0x{authored.item_id:02X} bit-exact, with 0x00CD and 0x0000 unchanged"
            )
            if content:
                print(
                    f"  issue #6 content example passed: the authored record "
                    f"(uses/type/attributes/icon, and no shared message bound) "
                    f"matches the running ROM, the production GetItemName() "
                    f"returned exactly the authored original name "
                    f"{authored.authoring_name!r} (len={authored.name_len}, "
                    f"fnv1a32=0x{authored.name_hash:08x}) from the generated "
                    f"content text table, and the bundled mechanic registered "
                    f"through the public API granted its bounded "
                    f"+{contract.avoid_bonus} avoid to the item's bearer only "
                    f"(control unit +0), with the content-free sample's "
                    f"+{contract.defense_bonus} defence unchanged for both"
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
            if content:
                print(
                    f"  issue #6 content example (boot half) passed: "
                    f"FE8_EXPANSION_STARTER_CONTENT=1, typed bundled item "
                    f"0x{authored.item_id:02X}, and both mechanics registered "
                    f"through the public API with no rejected registration"
                )
        return 0
    except CheckError as exc:
        print(f"run_item_expansion_checks: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
