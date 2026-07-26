"""Single source of truth for extensible ID / count / cap contracts (Issue #10).

Owns one canonical, machine-readable description of every extensible ID
domain the expansion framework exposes -- storage width, signedness,
sentinel, technical maximum, and the currently configured finite cap --
plus the per-consumer audit rows that prove no runtime table, event
operand, save field, UI buffer, lookup table, or link/network
representation silently truncates an expanded ID.

From this one description it deterministically renders three surfaces:

  * include/id_space.h            committed C89/agbcc-safe typedefs plus
                                  width/signedness/sentinel/max/cap macros
                                  and compile-time cap-fits-storage checks.
  * reports/id_space_audit.json   machine-readable consumer audit.
  * reports/id_space_audit.md     human audit, generated from the same rows.

Stdlib-only. Emitted C uses block comments only (never line comments), so
it stays agbcc / C89 safe. Regenerate or verify through the CLI:

    python3 -m scripts.generated_data.idspace generate
    python3 -m scripts.generated_data.idspace check

The item-domain cap constants below are the single source consumed by
scripts/generated_data/items/schema.py so the pilot expansion and this
contract can never disagree on the numbers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

C_HEADER_PATH = os.path.join(REPO_ROOT, "include", "id_space.h")
AUDIT_JSON_PATH = os.path.join(REPO_ROOT, "reports", "id_space_audit.json")
AUDIT_MD_PATH = os.path.join(REPO_ROOT, "reports", "id_space_audit.md")

SCHEMA_VERSION = 1

# Item domain caps, single-sourced here (see items/schema.py).
ITEM_TECHNICAL_MAX = 0xFF
ITEM_DEFAULT_CAP = 0xCD
ITEM_EXPANSION_FIRST = 0xCE
ITEM_CAP_ENV = "FE8_ITEM_ID_CAP"


class CapError(Exception):
    """A requested cap does not fit the domain storage/sentinel/capacity."""


class Evidence:
    def __init__(self, category, path, symbol, runtime_evidence=None):
        self.category = category
        self.path = path
        self.symbol = symbol
        # What has actually been observed carrying an expanded ID in a
        # booted ROM (never a plan or an intention). Recorded here so the
        # machine audit distinguishes "host-modelled" from "runtime-proven";
        # the producing gate is expansion-modern-itemexpansion-check
        # (tools/gba-playtest/run_item_expansion_checks.py).
        self.runtime_evidence = runtime_evidence

    def to_dict(self):
        return {
            "category": self.category,
            "path": self.path,
            "symbol": self.symbol,
            "runtime_evidence": self.runtime_evidence,
        }


class Domain:
    def __init__(self, key, title, id_ctype, storage_bits, signed, sentinel,
                 sentinel_name, technical_max, configured_cap, status,
                 default_behavior, count_ctype, count_bits, record_capacity=None,
                 partition_stride=None, freeze_reason=None, budget=None,
                 opt_in_first=None, evidence=()):
        self.key = key
        self.title = title
        self.id_ctype = id_ctype
        self.storage_bits = storage_bits
        self.signed = signed
        self.sentinel = sentinel
        self.sentinel_name = sentinel_name
        self.technical_max = technical_max
        self.configured_cap = configured_cap
        self.status = status
        self.default_behavior = default_behavior
        self.count_ctype = count_ctype
        self.count_bits = count_bits
        self.record_capacity = record_capacity
        self.partition_stride = partition_stride
        self.freeze_reason = freeze_reason
        self.budget = budget
        self.opt_in_first = opt_in_first
        self.evidence = list(evidence)

    @property
    def macro(self):
        return self.key.upper()

    def to_dict(self):
        return {
            "key": self.key,
            "title": self.title,
            "id_ctype": self.id_ctype,
            "storage_bits": self.storage_bits,
            "signed": self.signed,
            "sentinel": self.sentinel,
            "sentinel_name": self.sentinel_name,
            "technical_max": self.technical_max,
            "configured_cap": self.configured_cap,
            "status": self.status,
            "default_behavior": self.default_behavior,
            "count_ctype": self.count_ctype,
            "count_bits": self.count_bits,
            "record_capacity": self.record_capacity,
            "partition_stride": self.partition_stride,
            "freeze_reason": self.freeze_reason,
            "budget": self.budget,
            "opt_in_first": self.opt_in_first,
            "evidence": [e.to_dict() for e in self.evidence],
        }


DOMAINS = [
    Domain(
        key="character", title="Character (unit logical ID)",
        id_ctype="u8", storage_bits=8, signed=0, sentinel=0,
        sentinel_name="CHARACTER_NONE", technical_max=0xFF, configured_cap=0xFF,
        status="at-storage-max",
        default_behavior="256 records; index 0xFF is unreachable padding.",
        count_ctype="u16", count_bits=16, record_capacity=256,
        freeze_reason=("Logical ID storage is a full 8-bit byte "
                       "(GameSavePackedUnit.pid); 0x100+ needs a wider ID "
                       "field across runtime and save, out of pilot scope."),
        budget="0 runtime bytes: already at the 8-bit storage ceiling.",
        evidence=[
            Evidence("save-field", "include/bmsave.h", "GameSavePackedUnit.pid (u8)"),
            Evidence("lookup-table", "scripts/generated_data/characters/schema.py",
                     "gCharacterData[] record_budget=256"),
        ],
    ),
    Domain(
        key="class", title="Class (job) ID",
        id_ctype="u8", storage_bits=7, signed=0, sentinel=0,
        sentinel_name="CLASS_NONE", technical_max=0x7F, configured_cap=0x7F,
        status="frozen",
        default_behavior="0x00..0x7F; class 0x80 truncates on save.",
        count_ctype="u8", count_bits=8,
        freeze_reason=("GameSavePackedUnit.jid is a 7-bit save bitfield; "
                       "0x80 silently truncates to 0x00 on save. Widening "
                       "needs a save layout/epoch change, out of pilot scope."),
        budget="0 runtime bytes; capped at the 7-bit jid save field.",
        evidence=[
            Evidence("save-field", "include/bmsave.h", "GameSavePackedUnit.jid (7-bit)"),
            Evidence("lookup-table", "src/data/classes.json", "gClassData[]"),
        ],
    ),
    Domain(
        key="item", title="Item ID",
        id_ctype="u8", storage_bits=8, signed=0, sentinel=0,
        sentinel_name="ITEM_NONE", technical_max=ITEM_TECHNICAL_MAX,
        configured_cap=ITEM_DEFAULT_CAP, status="expandable",
        default_behavior=("Default cap 0xCD (206 vanilla records). Opt-in "
                          "FE8_ITEM_ID_CAP raises the cap up to 0xFF."),
        count_ctype="u16", count_bits=16, opt_in_first=ITEM_EXPANSION_FIRST,
        budget=("0xCD->0xCE costs +1 struct ItemData record in ROM and 0 "
                "RAM/save-layout bytes: item save fields are already 14-bit "
                "(0x3FFF) and the runtime index is masked to 8 bits."),
        evidence=[
            Evidence("runtime-macro", "include/bmitem.h", "ITEM_INDEX(x) = x & 0xFF",
                     runtime_evidence="modern debug+release ROM: GetItemIndex(MakeNewItem(0xCE)) == 0xCE"),
            Evidence("runtime-struct", "include/bmunit.h", "struct Unit.items[UNIT_ITEM_COUNT] (u16)",
                     runtime_evidence="modern debug ROM: Chapter 2 unit inventory slot holds 0x01CE"),
            Evidence("save-field", "include/bmsave.h", "GameSavePackedUnit.item1..item5 (14-bit)",
                     runtime_evidence="modern debug ROM: game-save pack/unpack roundtrip keeps 0x01CE, 14-bit field reads back 0x01CE"),
            Evidence("save-field", "include/bmsave.h", "SuspendSavePackedUnit.item1..item5",
                     runtime_evidence="modern debug ROM: suspend encode/decode roundtrip keeps 0x01CE"),
            Evidence("event-operand", "include/eventscript.h", "_EvtParams2 (16-bit lanes)",
                     runtime_evidence="modern debug ROM: EV_CMD_GIVEITEM decoded 0xCE into a live unit inventory"),
            Evidence("lookup-table", "src/data/items.json", "gItemData[] index-designated",
                     runtime_evidence="modern debug+release ROM: GetItemData(0xCE)->number == 0xCE (207-record linked table)"),
            Evidence("ui-buffer", "include/bmitem.h", "ItemData.nameTextId (u16) + iconId (u8)",
                     runtime_evidence="modern debug ROM: DrawItemMenuLine/DrawItemStatScreenLine drew 0xCE into the live BG0 tilemap"),
            Evidence("link-network", "include/bmsave.h", "MultiArenaSaveTeam.units[] (GameSavePackedUnit)",
                     runtime_evidence="modern debug ROM: MultiArena team write+read through SRAM keeps 0x01CE"),
        ],
    ),
    Domain(
        key="chapter", title="Chapter ID",
        id_ctype="s8", storage_bits=7, signed=1, sentinel=-1,
        sentinel_name="CHAPTER_NONE", technical_max=0x7F, configured_cap=0x7F,
        status="frozen",
        default_behavior="0x00..0x7F positive; negative values reserved as sentinels.",
        count_ctype="u8", count_bits=8,
        freeze_reason=("PlaySt.chapterIndex is s8; negatives are reserved "
                       "sentinels, so the positive range caps at 0x7F. "
                       "Widening needs a signed->wider save/runtime change."),
        budget="0 runtime bytes; capped at the signed 8-bit chapter field.",
        evidence=[
            Evidence("runtime-struct", "include/types.h", "PlaySt.chapterIndex (s8)"),
            Evidence("save-field", "include/savemenu.h", "chapter_idx[3]"),
            Evidence("external-interface", "include/eventscript.h", "EvtGetChapterIndex"),
        ],
    ),
    Domain(
        key="unit", title="Unit (deployment) ID slot",
        id_ctype="u8", storage_bits=8, signed=0, sentinel=0x40,
        sentinel_name="FACTION_STRIDE", technical_max=0x3F, configured_cap=0x3F,
        status="frozen",
        default_behavior="0x00..0x3F per faction; 0x40 is the next faction base.",
        count_ctype="u8", count_bits=8, partition_stride=0x40,
        freeze_reason=("Unit IDs are partitioned into 0x40-wide faction "
                       "blocks (FACTION_BLUE/GREEN/RED/PURPLE); a per-faction "
                       "id at 0x40 collides with the next faction base."),
        budget="0 runtime bytes; capped by the 0x40 faction partition stride.",
        evidence=[
            Evidence("runtime-struct", "include/bmunit.h", "FACTION_BLUE/GREEN/RED/PURPLE (0x40 stride)"),
            Evidence("save-field", "include/sram-layout.h", "UNIT_SAVE_AMOUNT_* * sizeof(packed unit)"),
        ],
    ),
    Domain(
        key="event", title="Event operand lane",
        id_ctype="u16", storage_bits=16, signed=0, sentinel=None,
        sentinel_name=None, technical_max=0xFFFF, configured_cap=0xFF,
        status="adequate",
        default_behavior="16-bit lanes; carries any 8-bit ID domain with headroom.",
        count_ctype="u16", count_bits=16,
        budget="0 bytes: operand lanes are already 16-bit; item IDs fit trivially.",
        evidence=[
            Evidence("event-operand", "include/eventscript.h", "_EvtParams2 / _EvtArg0"),
            Evidence("external-interface", "include/EAstdlib.h", "GIVEITEMTO / EvtGiveItemAtSlot3",
                     runtime_evidence="modern debug ROM: a real GIVEITEMTO script ran through the production event engine with operand 0xCE"),
        ],
    ),
]

REQUIRED_CATEGORIES = (
    "runtime-macro", "runtime-struct", "save-field", "event-operand",
    "lookup-table", "ui-buffer", "link-network", "external-interface",
)


def domain_by_key(key):
    for domain in DOMAINS:
        if domain.key == key:
            return domain
    raise KeyError(key)


def consumer_rows():
    """Flatten (domain x evidence) into deterministic per-consumer audit rows."""
    rows = []
    for domain in DOMAINS:
        for ev in domain.evidence:
            rows.append({
                "domain": domain.key,
                "category": ev.category,
                "path": ev.path,
                "symbol": ev.symbol,
                "storage_bits": domain.storage_bits,
                "signed": domain.signed,
                "sentinel": domain.sentinel,
                "technical_max": domain.technical_max,
                "configured_cap": domain.configured_cap,
                "status": domain.status,
                "default_behavior": domain.default_behavior,
                "budget": domain.budget,
                "runtime_evidence": ev.runtime_evidence,
            })
    rows.sort(key=lambda r: (r["domain"], r["category"], r["path"], r["symbol"]))
    return rows


def resolve_item_id_cap(env=None):
    """Resolve the active item ID cap. Default (no override) is the vanilla
    0xCD; an explicit FE8_ITEM_ID_CAP opts into expansion (validated)."""
    env = os.environ if env is None else env
    raw = env.get(ITEM_CAP_ENV)
    if raw is None or raw == "":
        return ITEM_DEFAULT_CAP
    try:
        cap = int(raw, 0)
    except ValueError:
        raise CapError(
            "{} value {!r} is not an integer".format(ITEM_CAP_ENV, raw)
        )
    validate_domain_cap(domain_by_key("item"), cap)
    return cap


def validate_domain_cap(domain, cap):
    """Raise CapError if cap does not fit the domain. Returns cap on success."""
    if not isinstance(cap, int):
        raise CapError("{} cap must be an integer".format(domain.key))
    if cap < 0:
        raise CapError("{} cap {} must be >= 0".format(domain.key, cap))
    if cap > domain.technical_max:
        raise CapError(
            "{} cap 0x{:X} exceeds the technical maximum 0x{:X} "
            "({}-bit {} storage would silently truncate it)".format(
                domain.key, cap, domain.technical_max, domain.storage_bits,
                "signed" if domain.signed else "unsigned"))
    if domain.partition_stride is not None and cap >= domain.partition_stride:
        raise CapError(
            "{} cap 0x{:X} collides with the 0x{:X} partition stride "
            "(next-faction base / sentinel)".format(
                domain.key, cap, domain.partition_stride))
    if domain.record_capacity is not None and cap + 1 > domain.record_capacity:
        raise CapError(
            "{} cap 0x{:X} implies {} records but the fixed capacity is {}".format(
                domain.key, cap, cap + 1, domain.record_capacity))
    return cap


def validate_all_configured_caps():
    """Validate every domain configured_cap against its own storage."""
    for domain in DOMAINS:
        validate_domain_cap(domain, domain.configured_cap)


def digest():
    payload = {
        "schema_version": SCHEMA_VERSION,
        "domains": [d.to_dict() for d in DOMAINS],
        "consumers": consumer_rows(),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _cap_hex(value):
    if value is None:
        return "-"
    if value < 0:
        return str(value)
    return "0x{:02X}".format(value)


def render_audit_json():
    payload = {
        "schema_version": SCHEMA_VERSION,
        "digest": digest(),
        "required_categories": list(REQUIRED_CATEGORIES),
        "domains": [d.to_dict() for d in DOMAINS],
        "consumers": consumer_rows(),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_audit_markdown():
    lines = []
    lines.append("# Extensible ID space audit (Issue #10)\n\n")
    lines.append("_Auto-generated by `python3 -m scripts.generated_data.idspace "
                 "generate`. Do not edit by hand -- edit "
                 "`scripts/generated_data/idspace.py` and regenerate._\n\n")
    lines.append("Single machine+human source describing every extensible ID "
                 "domain and every consumer that must not silently truncate an "
                 "expanded ID.\n\n")
    lines.append("- Schema version: {}\n".format(SCHEMA_VERSION))
    lines.append("- Audit digest (sha256): `{}`\n\n".format(digest()))
    lines.append("## Domains\n\n")
    lines.append("| Domain | C type | Bits | Signed | Sentinel | Technical max "
                 "| Configured cap | Status | Budget |\n")
    lines.append("|---|---|---|---|---|---|---|---|---|\n")
    for d in DOMAINS:
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |\n".format(
            d.key, d.id_ctype, d.storage_bits, "yes" if d.signed else "no",
            _cap_hex(d.sentinel), _cap_hex(d.technical_max),
            _cap_hex(d.configured_cap), d.status, d.budget or "-"))
    lines.append("\n## Consumers\n\n")
    lines.append("| Domain | Category | Path | Symbol | Bits | Sentinel "
                 "| Max safe cap | Configured cap | Status | Runtime evidence |\n")
    lines.append("|---|---|---|---|---|---|---|---|---|---|\n")
    for r in consumer_rows():
        lines.append("| {} | {} | `{}` | {} | {} | {} | {} | {} | {} | {} |\n".format(
            r["domain"], r["category"], r["path"], r["symbol"], r["storage_bits"],
            _cap_hex(r["sentinel"]), _cap_hex(r["technical_max"]),
            _cap_hex(r["configured_cap"]), r["status"],
            r["runtime_evidence"] or "host-modelled only"))
    lines.append("\n## Frozen domains and future work\n\n")
    for d in DOMAINS:
        if d.freeze_reason:
            lines.append("- **{}**: {}\n".format(d.key, d.freeze_reason))
    return "".join(lines)


def render_c_header():
    out = []
    out.append("/* AUTO-GENERATED by scripts/generated_data/idspace.py -- DO NOT EDIT BY HAND.\n")
    out.append(" * Public typed ID / count / cap contract for Issue #10.\n")
    out.append(" * Regenerate with: python3 -m scripts.generated_data.idspace generate\n")
    out.append(" */\n")
    out.append("#ifndef GUARD_ID_SPACE_H\n")
    out.append("#define GUARD_ID_SPACE_H\n\n")
    out.append("#include \"gba/types.h\"\n\n")
    out.append("/* Compile-time assertion (C89-safe negative-array-size trick). */\n")
    out.append("#define ID_SPACE_STATIC_ASSERT(cond, tag) \\\n")
    out.append("    typedef char id_space_static_assert_##tag[(cond) ? 1 : -1]\n\n")
    for d in DOMAINS:
        m = d.macro
        out.append("/* {} */\n".format(d.title))
        out.append("typedef {} {}Id;\n".format(d.id_ctype, _camel(d.key)))
        out.append("typedef {} {}Count;\n".format(d.count_ctype, _camel(d.key)))
        out.append("#define {}_ID_STORAGE_BITS {}\n".format(m, d.storage_bits))
        out.append("#define {}_ID_SIGNED {}\n".format(m, d.signed))
        if d.sentinel is not None:
            out.append("#define {}_ID_SENTINEL {}\n".format(m, d.sentinel))
        out.append("#define {}_ID_TECHNICAL_MAX {}\n".format(m, _hexlit(d.technical_max)))
        if d.key == "item":
            # The item cap is the one expandable build input. Emit it as a
            # build-time-overridable macro keyed to FE8_ITEM_ID_CAP (default
            # 0xCD) instead of a baked-in literal, so:
            #   * the committed header is cap-invariant (no drift when a build
            #     opts into 0xCE..0xFF), and
            #   * the generator (resolve_item_id_cap, same env var) and this
            #     compiled consumer resolve one single cap value.
            # The compile-time assert below then validates the *build-time*
            # cap (e.g. -DFE8_ITEM_ID_CAP=0x100 fails 0x100 <= 0xFF), so the
            # contract is live code, not a dead literal check.
            out.append("#ifndef {}\n".format(ITEM_CAP_ENV))
            out.append("#define {} {}\n".format(ITEM_CAP_ENV, _hexlit(d.configured_cap)))
            out.append("#endif\n")
            out.append("#define {}_ID_CONFIGURED_CAP {}\n".format(m, ITEM_CAP_ENV))
        else:
            out.append("#define {}_ID_CONFIGURED_CAP {}\n".format(m, _hexlit(d.configured_cap)))
        if d.opt_in_first is not None:
            out.append("#define {}_ID_EXPANSION_FIRST {}\n".format(m, _hexlit(d.opt_in_first)))
        out.append("\n")
    out.append("/* Cap-fits-storage guarantees checked at compile time. */\n")
    out.append("ID_SPACE_STATIC_ASSERT(ITEM_ID_CONFIGURED_CAP <= ITEM_ID_TECHNICAL_MAX, item_cap_fits);\n")
    out.append("ID_SPACE_STATIC_ASSERT(ITEM_ID_TECHNICAL_MAX <= 0x3FFF, item_fits_save14);\n")
    out.append("ID_SPACE_STATIC_ASSERT(CLASS_ID_CONFIGURED_CAP <= 0x7F, class_cap_fits_jid7);\n")
    out.append("ID_SPACE_STATIC_ASSERT(CHARACTER_ID_CONFIGURED_CAP <= 0xFF, character_cap_fits_u8);\n")
    out.append("ID_SPACE_STATIC_ASSERT(CHAPTER_ID_CONFIGURED_CAP <= 0x7F, chapter_cap_fits_s8);\n")
    out.append("ID_SPACE_STATIC_ASSERT(UNIT_ID_CONFIGURED_CAP < 0x40, unit_cap_fits_faction);\n\n")
    out.append("#endif /* GUARD_ID_SPACE_H */\n")
    return "".join(out)


def _camel(key):
    return "".join(part.capitalize() for part in key.split("_"))


def _hexlit(value):
    if value is None:
        return "0"
    if value < 0:
        return str(value)
    return "0x{:X}".format(value)


def write_if_changed(path, content):
    existing = None
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    if existing == content:
        return False
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return True


def _outputs():
    return [
        (C_HEADER_PATH, render_c_header()),
        (AUDIT_JSON_PATH, render_audit_json()),
        (AUDIT_MD_PATH, render_audit_markdown()),
    ]


def cmd_generate(_args):
    validate_all_configured_caps()
    for path, content in _outputs():
        changed = write_if_changed(path, content)
        rel = os.path.relpath(path, REPO_ROOT)
        print("{} {}".format("wrote" if changed else "up-to-date", rel))
    return 0


def cmd_check(_args):
    validate_all_configured_caps()
    drift = []
    for path, content in _outputs():
        rel = os.path.relpath(path, REPO_ROOT)
        if not os.path.exists(path):
            drift.append("missing: {}".format(rel))
            continue
        with open(path, "r", encoding="utf-8") as handle:
            on_disk = handle.read()
        if on_disk != content:
            drift.append("stale: {} (regenerate with idspace generate)".format(rel))
    if drift:
        for item in drift:
            print(item, file=sys.stderr)
        print("FAILED: {} id-space drift item(s)".format(len(drift)), file=sys.stderr)
        return 1
    print("id-space contract up-to-date ({} outputs)".format(len(_outputs())))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m scripts.generated_data.idspace")
    sub = parser.add_subparsers(dest="command")
    gen = sub.add_parser("generate", help="write the committed C header + audit files")
    gen.set_defaults(func=cmd_generate)
    chk = sub.add_parser("check", help="fail on cap violation or committed-output drift")
    chk.set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except CapError as exc:
        print("id-space cap error: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
