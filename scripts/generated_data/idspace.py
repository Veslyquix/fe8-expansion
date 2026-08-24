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
import re
import sys

from . import consumer_census

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

C_HEADER_PATH = os.path.join(REPO_ROOT, "include", "id_space.h")
AUDIT_JSON_PATH = os.path.join(REPO_ROOT, "reports", "id_space_audit.json")
AUDIT_MD_PATH = os.path.join(REPO_ROOT, "reports", "id_space_audit.md")

# Build-local ACTIVE contract (never committed): what *this* configured build
# actually resolved, as opposed to the committed DEFAULT contract above. The
# committed surfaces stay byte-identical at every cap so a configured build can
# never introduce tracked drift; the active surfaces are the ones that carry
# 0xCE / 207 records when FE8_ITEM_ID_CAP opts in.
ACTIVE_OUT_DIR = os.path.join(REPO_ROOT, "build", "generated", "data")
ACTIVE_JSON_NAME = "id_space_active_audit.json"
ACTIVE_MD_NAME = "id_space_active_audit.md"
ACTIVE_HEADER_NAME = "id_space_active.h"

SCHEMA_VERSION = 2

# Which registered generated-data table (if any) holds a domain records, so the
# active audit can report the *actually loaded* record count instead of a
# hand-maintained number. Domains with no single record table report an honest
# n/a plus the reason below -- never a silent blank.
DOMAIN_RECORD_TABLES = {
    "character": "characters",
    "class": "classes",
    "item": "items",
}
DOMAIN_RECORD_NA_REASONS = {
    "chapter": ("no single record table: chapter data is authored per chapter in "
                "src/data/chapter_settings.h, so the cap -- not a record count -- "
                "is the contract"),
    "unit": ("no single record table: deployment slots are per-chapter event unit "
             "definitions; the 0x40 faction stride is the contract"),
    "event": ("no record table: an event operand lane is a transport width, not a "
              "table of records"),
}

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
        id_ctype="u8", storage_bits=8, signed=0, sentinel=0,
        sentinel_name="CLASS_NONE", technical_max=0xFF, configured_cap=0xFF,
        status="expandable",
        default_behavior=("0x00..0xFF. GameSavePackedUnit.jid is a full "
                          "8-bit byte when FE8_PURCHASE_GENERICS is enabled "
                          "(the modern default); classes 0x80+ round-trip "
                          "through a real save exactly like 0x00..0x7F. "
                          "When FE8_PURCHASE_GENERICS is disabled, or in the "
                          "archival agbcc lane (which never defines it), jid "
                          "stays the original 7-bit bitfield -- classes "
                          "0x80+ must never be assigned to a real, "
                          "save-persisted roster Unit in that configuration. "
                          "The two classes currently using this range, "
                          "CLASS_CAMP and CLASS_TENT_STRUCTURE, satisfy this "
                          "by construction: like the pre-existing "
                          "CLASS_OBSTACLE, they are only ever assigned to a "
                          "transient, non-persisted fake battle unit "
                          "(built for trap combat), never to a deployed "
                          "roster Unit, in any configuration."),
        count_ctype="u8", count_bits=8,
        budget=("0 runtime bytes for GameSavePackedUnit when "
                "FE8_PURCHASE_GENERICS is disabled or in the archival lane "
                "(struct unchanged); +1 byte per packed unit record when "
                "enabled (jid moves out of the bitfield into its own byte) "
                "-- see include/bmsave.h and EXPANSION_SAVE_COMPAT_EPOCH."),
        evidence=[
            Evidence("save-field", "include/bmsave.h",
                     "GameSavePackedUnit.jid (8-bit when FE8_PURCHASE_GENERICS, else 7-bit)"),
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


def evidence_rows():
    """Curated, runtime-proven evidence rows (domain x evidence).

    These are the rows a booted ROM actually exercised; they are deliberately
    *not* the coverage proof -- see :func:`consumer_rows`, which is generated
    from the source-driven census so a missed consumer fails the build.
    """
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


def consumer_rows(caps=None, counts=None):
    """Every source-scanned consumer, joined with its classification.

    One fact source (scripts/generated_data/consumer_census.py plus the tracked
    consumer_classification.json) feeds both audits; ``caps``/``counts`` swap
    the DEFAULT contract numbers for this build ACTIVE ones without changing a
    single row, so the two audits can never disagree about *who* consumes an
    ID -- only about which cap/count is in force.
    """
    caps = caps or {d.key: d.configured_cap for d in DOMAINS}
    # Default (committed) rows carry the DEFAULT record counts, so the audit
    # never shows a bare n/a where a real, env-independent count exists.
    if counts is None:
        counts = {d.key: default_record_count(d.key) for d in DOMAINS}
    rows = []
    for row in consumer_census.classified_rows():
        domain = domain_by_key(row["domain"])
        rows.append({
            "key": row["key"],
            "domain": row["domain"],
            "category": row["category"],
            "reason": row["reason"],
            "kind": row["kind"],
            "path": row["path"],
            "symbol": row["symbol"],
            "declaration": row["declaration"],
            "line": row["line"],
            "surface": row["surface"],
            "storage_bits": domain.storage_bits,
            "signed": domain.signed,
            "sentinel": domain.sentinel,
            "technical_max": domain.technical_max,
            "configured_cap": caps.get(row["domain"], domain.configured_cap),
            "record_count": counts.get(row["domain"]),
            "status": domain.status,
        })
    rows.sort(key=lambda r: (r["domain"], r["category"], r["path"], r["kind"], r["symbol"]))
    return rows


_RECORD_COUNT_CACHE = {}


def _load_table_record_count(table):
    """Actual number of records the registered table loads right now.

    Cached per (table, resolved item cap) because the items table content is
    cap-dependent: at FE8_ITEM_ID_CAP>=0xCE it merges the expansion overlay.
    """
    from .schema import REGISTRY
    from . import registry  # noqa: F401  (import registers table schemas)
    cache_key = (table, os.environ.get(ITEM_CAP_ENV, ""))
    if cache_key not in _RECORD_COUNT_CACHE:
        schema = REGISTRY.resolve(table)
        _RECORD_COUNT_CACHE[cache_key] = len(schema.load_records(schema.default_source))
    return _RECORD_COUNT_CACHE[cache_key]


def default_record_count(domain_key):
    """Record count of the committed DEFAULT contract (never env-dependent)."""
    table = DOMAIN_RECORD_TABLES.get(domain_key)
    if table is None:
        return None
    if domain_key == "item":
        # Explicitly load at the vanilla cap so the committed number stays 206
        # whatever FE8_ITEM_ID_CAP says in this shell.
        from .items import schema as items_schema
        return len(items_schema.load_records(
            items_schema.ItemsTableSchema.default_source, item_cap=ITEM_DEFAULT_CAP))
    return _load_table_record_count(table)


def active_record_count(domain_key, env=None):
    """Record count this configured build actually loads (env-dependent)."""
    table = DOMAIN_RECORD_TABLES.get(domain_key)
    if table is None:
        return None
    if domain_key == "item":
        from .items import schema as items_schema
        return len(items_schema.load_records(
            items_schema.ItemsTableSchema.default_source,
            item_cap=resolve_item_id_cap(env)))
    return _load_table_record_count(table)


def active_caps(env=None):
    """Resolved ACTIVE cap per domain (only `item` is a build input today)."""
    caps = {}
    for domain in DOMAINS:
        if domain.key == "item":
            caps[domain.key] = resolve_item_id_cap(env)
        else:
            caps[domain.key] = domain.configured_cap
    return caps


def active_manifest_rows(env=None):
    """Registry view for THIS build: committed manifest count vs actual load.

    reports/generated_data_manifest.md deliberately stays at the committed
    default (items: 206) so an opted-in build introduces no tracked drift --
    which is exactly why the ACTIVE surfaces have to publish the real number
    (items: 207 at cap 0xCE) instead of leaving downstream tools to read 206
    and believe it.
    """
    from .schema import REGISTRY
    from . import registry  # noqa: F401  (import registers table schemas)
    rows = []
    for name in REGISTRY.all_names():
        schema = REGISTRY.resolve(name)
        if name == "items":
            from .items import schema as items_schema
            records = items_schema.load_records(
                schema.default_source, item_cap=resolve_item_id_cap(env),
                overlay_source=items_schema.ITEMS_EXPANSION_SOURCE)
        else:
            records = schema.load_records(schema.default_source)
        committed = schema.manifest_record_count(records)
        active = len(records)
        rows.append({
            "table": name,
            "committed_record_count": committed,
            "active_record_count": active,
            "differs_from_committed": committed != active,
        })
    rows.sort(key=lambda r: r["table"])
    return rows


def _active_domain_entries(env=None):
    """Per-domain ACTIVE cap/count model for THIS build -- census-free.

    Deliberately excludes the consumer census (the ~15 MB source walk): this
    is the cap/record-count contract only, computed from resolve_item_id_cap
    and the registered record tables (a fraction of a second). active_contract
    layers the expensive census on top; the cheap `active-heal` probe reuses
    exactly this model so the two can never disagree on the numbers.
    """
    caps = active_caps(env)
    domains = []
    counts = {}
    for domain in DOMAINS:
        default_count = default_record_count(domain.key)
        count = active_record_count(domain.key, env)
        counts[domain.key] = count
        entry = {
            "key": domain.key,
            "title": domain.title,
            "id_ctype": domain.id_ctype,
            "storage_bits": domain.storage_bits,
            "signed": domain.signed,
            "sentinel": domain.sentinel,
            "technical_max": domain.technical_max,
            "status": domain.status,
            "default_cap": domain.configured_cap,
            # Hex twins: the numeric fields are what tools compare, but every
            # human-facing spelling of a cap in this project is hex, so a
            # grep/jq for 0xCE must hit in the machine audit too.
            "default_cap_hex": _cap_hex(domain.configured_cap),
            "default_record_count": default_count,
            "active_configured_cap": caps[domain.key],
            "active_configured_cap_hex": _cap_hex(caps[domain.key]),
            "active_record_count": count,
            "record_count_status": "counted" if count is not None else "n/a",
            "record_count_note": DOMAIN_RECORD_NA_REASONS.get(domain.key),
            "record_table": DOMAIN_RECORD_TABLES.get(domain.key),
            "expanded_past_default": caps[domain.key] != domain.configured_cap,
        }
        domains.append(entry)
    return domains, caps, counts


def active_contract(env=None):
    """Full machine model of the ACTIVE (this build) cap/count contract."""
    domains, caps, counts = _active_domain_entries(env)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "contract": "active",
        "contract_note": (
            "Build-local ACTIVE contract for this configured build. The committed "
            "DEFAULT contract lives in reports/id_space_audit.{json,md} and "
            "include/id_space.h and never changes with FE8_ITEM_ID_CAP."),
        "item_cap_env": ITEM_CAP_ENV,
        "item_cap_env_value": (env if env is not None else os.environ).get(ITEM_CAP_ENV) or None,
        "domains": domains,
        "manifest": active_manifest_rows(env),
        "census": consumer_census.scan_scope(),
        "census_digest": consumer_census.census_digest(),
        "consumers": consumer_rows(caps=caps, counts=counts),
    }
    return payload


def validate_active_contract(payload):
    """Fail on an ACTIVE contract that cannot be true (cap/count mismatch)."""
    for domain in payload["domains"]:
        cap = domain["active_configured_cap"]
        count = domain["active_record_count"]
        if count is None:
            continue
        if count > cap + 1:
            raise CapError(
                "{} domain loads {} record(s) but the active cap 0x{:02X} only "
                "addresses {} ID(s); raise the cap or drop records".format(
                    domain["key"], count, cap, cap + 1))


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
        "evidence": evidence_rows(),
        "census_digest": consumer_census.census_digest(),
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
        "contract": "default",
        "contract_note": (
            "Committed DEFAULT contract: the vanilla cap/count every checkout "
            "and the archival lane compile against. It is deliberately "
            "env-independent -- a build that opts into FE8_ITEM_ID_CAP>=0xCE "
            "reads the build-local ACTIVE contract "
            "(build/generated/data/id_space_active_audit.json and "
            "id_space_active.h) instead, and never rewrites this file."),
        "default_item_cap": ITEM_DEFAULT_CAP,
        "default_item_record_count": default_record_count("item"),
        "digest": digest(),
        "required_categories": list(REQUIRED_CATEGORIES),
        "domains": [d.to_dict() for d in DOMAINS],
        "domain_record_counts": {
            d.key: {
                "default_record_count": default_record_count(d.key),
                "record_count_status": "counted" if default_record_count(d.key) is not None else "n/a",
                "record_count_note": DOMAIN_RECORD_NA_REASONS.get(d.key),
            }
            for d in DOMAINS
        },
        "evidence": evidence_rows(),
        "census": consumer_census.scan_scope(),
        "census_digest": consumer_census.census_digest(),
        "consumers": consumer_rows(),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_census_sections(lines, rows, scope):
    """Shared census rendering for the DEFAULT and ACTIVE human audits."""
    audited = [r for r in rows if r["category"] != consumer_census.EXCLUSION_CATEGORY]
    excluded = [r for r in rows if r["category"] == consumer_census.EXCLUSION_CATEGORY]
    lines.append("\n## Source-driven consumer census\n\n")
    lines.append("Every row below comes from scanning the real source tree "
                 "(`python3 -m scripts.generated_data.consumer_census scan`) and is "
                 "mapped 1:1 to a category in "
                 "`scripts/generated_data/consumer_classification.json`. A new "
                 "declaration that names an ID domain fails "
                 "`generated-data-check` until it is classified; a classified row "
                 "that disappears fails as stale.\n\n")
    lines.append("- Scanned hits: {} ({} audited, {} reviewed exclusions)\n".format(
        len(rows), len(audited), len(excluded)))
    lines.append("- Census digest (sha256): `{}`\n".format(consumer_census.census_digest()))
    lines.append("- Scan roots: {}\n".format(", ".join(
        "`{}` ({})".format(root["root"], "/".join(root["extensions"])) for root in scope["roots"])))
    lines.append("- Excluded by configuration: {}\n".format(", ".join(
        "`{}` ({})".format(item["prefix"], item["reason"]) for item in scope["excluded"])))
    lines.append("\n### Coverage limitations (honest scope)\n\n")
    for limitation in scope["coverage_limitations"]:
        lines.append("- {}\n".format(limitation))
    lines.append("\n### Category totals\n\n")
    lines.append("| Category | Rows |\n|---|---|\n")
    totals = {}
    for row in rows:
        totals[row["category"]] = totals.get(row["category"], 0) + 1
    for category in sorted(totals):
        lines.append("| {} | {} |\n".format(category, totals[category]))
    lines.append("\n### Consumers\n\n")
    lines.append("| Domain | Category | Kind | Path | Symbol | Bits | Cap | Records | Evidence line |\n")
    lines.append("|---|---|---|---|---|---|---|---|---|\n")
    for r in rows:
        count = r.get("record_count")
        lines.append("| {} | {} | {} | `{}` | `{}` | {} | {} | {} | {}:{} |\n".format(
            r["domain"], r["category"], r["kind"], r["path"], r["symbol"],
            r["storage_bits"], _cap_hex(r["configured_cap"]),
            count if count is not None else "n/a", r["path"], r["line"]))
    if excluded:
        lines.append("\n### Reviewed exclusions (same-named, carries no ID)\n\n")
        lines.append("| Path | Symbol | Reason |\n|---|---|---|\n")
        for r in excluded:
            lines.append("| `{}` | `{}` | {} |\n".format(r["path"], r["symbol"], r["reason"]))


def render_audit_markdown():
    lines = []
    lines.append("# Extensible ID space audit -- DEFAULT contract (Issue #10)\n\n")
    lines.append("_Auto-generated by `python3 -m scripts.generated_data.idspace "
                 "generate`. Do not edit by hand -- edit "
                 "`scripts/generated_data/idspace.py` / "
                 "`scripts/generated_data/consumer_classification.json` and "
                 "regenerate._\n\n")
    lines.append("**This file is the committed DEFAULT contract**: the vanilla "
                 "cap/count that every checkout, the archival agbcc lane and an "
                 "un-configured modern build compile against. It is "
                 "env-independent by design -- `FE8_ITEM_ID_CAP=0xCE` does *not* "
                 "rewrite it. A configured build publishes its own numbers in the "
                 "build-local ACTIVE contract "
                 "(`build/generated/data/id_space_active_audit.md`, "
                 "`id_space_active_audit.json`, `id_space_active.h`); read those "
                 "for the active cap/record count, never this file.\n\n")
    lines.append("- Schema version: {}\n".format(SCHEMA_VERSION))
    lines.append("- Default item cap / record count: {} / {}\n".format(
        _cap_hex(ITEM_DEFAULT_CAP), default_record_count("item")))
    lines.append("- Audit digest (sha256): `{}`\n\n".format(digest()))
    lines.append("## Domains (default contract)\n\n")
    lines.append("| Domain | C type | Bits | Signed | Sentinel | Technical max "
                 "| Default cap | Default records | Status | Budget |\n")
    lines.append("|---|---|---|---|---|---|---|---|---|---|\n")
    for d in DOMAINS:
        count = default_record_count(d.key)
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |\n".format(
            d.key, d.id_ctype, d.storage_bits, "yes" if d.signed else "no",
            _cap_hex(d.sentinel), _cap_hex(d.technical_max),
            _cap_hex(d.configured_cap),
            count if count is not None else "n/a",
            d.status, d.budget or "-"))
    lines.append("\nDomains with no record table report `n/a` for records: ")
    lines.append("; ".join("**{}** -- {}".format(key, reason)
                           for key, reason in sorted(DOMAIN_RECORD_NA_REASONS.items())))
    lines.append("\n\n## Runtime-proven evidence\n\n")
    lines.append("| Domain | Category | Path | Symbol | Runtime evidence |\n")
    lines.append("|---|---|---|---|---|\n")
    for r in evidence_rows():
        lines.append("| {} | {} | `{}` | {} | {} |\n".format(
            r["domain"], r["category"], r["path"], r["symbol"],
            r["runtime_evidence"] or "host-modelled only"))
    _render_census_sections(lines, consumer_rows(), consumer_census.scan_scope())
    lines.append("\n## Frozen domains and future work\n\n")
    for d in DOMAINS:
        if d.freeze_reason:
            lines.append("- **{}**: {}\n".format(d.key, d.freeze_reason))
    return "".join(lines)


def render_active_json(env=None):
    """Machine-readable ACTIVE audit for this configured build."""
    payload = active_contract(env)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_active_markdown(env=None):
    """Human ACTIVE audit -- same consumer rows, active cap/record counts."""
    payload = active_contract(env)
    lines = []
    lines.append("# Extensible ID space audit -- ACTIVE contract (Issue #10)\n\n")
    lines.append("_Auto-generated (build-local, never committed) by "
                 "`python3 -m scripts.generated_data.idspace active-generate`._\n\n")
    lines.append("**This is what the current build actually resolved.** The "
                 "committed DEFAULT contract (`reports/id_space_audit.md`, "
                 "`include/id_space.h`) stays at the vanilla numbers at every "
                 "cap; downstream tooling that needs the *active* cap/record "
                 "count must read this file, `id_space_active_audit.json`, or "
                 "the generated `id_space_active.h`.\n\n")
    lines.append("- `{}` = {}\n".format(
        ITEM_CAP_ENV, payload["item_cap_env_value"] or "(unset -- vanilla default)"))
    lines.append("- Census digest (sha256): `{}`\n\n".format(payload["census_digest"]))
    lines.append("## Domains: default vs active\n\n")
    lines.append("| Domain | Default cap | Default records | Active cap "
                 "| Active records | Expanded | Record source |\n")
    lines.append("|---|---|---|---|---|---|---|\n")
    for d in payload["domains"]:
        if d["record_count_status"] == "counted":
            source = "`{}` table".format(d["record_table"])
            default_count = str(d["default_record_count"])
            active_count = str(d["active_record_count"])
        else:
            source = "n/a -- {}".format(d["record_count_note"])
            default_count = "n/a"
            active_count = "n/a"
        lines.append("| {} | {} | {} | {} | {} | {} | {} |\n".format(
            d["key"], _cap_hex(d["default_cap"]), default_count,
            _cap_hex(d["active_configured_cap"]), active_count,
            "yes" if d["expanded_past_default"] else "no", source))
    lines.append("\n## Registry manifest: committed vs active record counts\n\n")
    lines.append("The committed `reports/generated_data_manifest.md` is pinned to "
                 "the default record counts so a configured build never rewrites "
                 "a tracked report. These are the counts this build actually "
                 "loaded.\n\n")
    lines.append("| Table | Committed manifest | Active (this build) | Differs |\n")
    lines.append("|---|---|---|---|\n")
    for row in payload["manifest"]:
        lines.append("| {} | {} | {} | {} |\n".format(
            row["table"], row["committed_record_count"], row["active_record_count"],
            "yes" if row["differs_from_committed"] else "no"))
    _render_census_sections(lines, payload["consumers"], payload["census"])
    return "".join(lines)


def render_active_header(env=None):
    """C89/agbcc-safe ACTIVE contract header consumed by the generated table."""
    payload = active_contract(env)
    out = []
    out.append("/* AUTO-GENERATED by scripts/generated_data/idspace.py -- DO NOT EDIT BY HAND.\n")
    out.append(" * Build-local ACTIVE id-space contract for THIS configured build.\n")
    out.append(" * The committed include/id_space.h holds the DEFAULT contract; this\n")
    out.append(" * header holds what {} actually resolved, so a compiled\n".format(ITEM_CAP_ENV))
    out.append(" * consumer can assert the generated table and the compiler agree.\n")
    out.append(" * Regenerate with: python3 -m scripts.generated_data.idspace active-generate\n")
    out.append(" */\n")
    out.append("#ifndef GUARD_ID_SPACE_ACTIVE_H\n")
    out.append("#define GUARD_ID_SPACE_ACTIVE_H\n\n")
    for d in payload["domains"]:
        macro = d["key"].upper()
        out.append("/* {} */\n".format(d["title"]))
        out.append("#define {}_ID_DEFAULT_CAP {}\n".format(macro, _hexlit(d["default_cap"])))
        out.append("#define {}_ID_ACTIVE_CONFIGURED_CAP {}\n".format(
            macro, _hexlit(d["active_configured_cap"])))
        if d["record_count_status"] == "counted":
            out.append("#define {}_ID_DEFAULT_RECORD_COUNT {}\n".format(
                macro, d["default_record_count"]))
            out.append("#define {}_ID_ACTIVE_RECORD_COUNT {}\n".format(
                macro, d["active_record_count"]))
        else:
            out.append("/* {}_ID_*_RECORD_COUNT: n/a -- {} */\n".format(
                macro, d["record_count_note"]))
        out.append("#define {}_ID_ACTIVE_EXPANDED {}\n".format(
            macro, 1 if d["expanded_past_default"] else 0))
        out.append("\n")
    out.append("#endif /* GUARD_ID_SPACE_ACTIVE_H */\n")
    return "".join(out)


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
    out.append("ID_SPACE_STATIC_ASSERT(CLASS_ID_CONFIGURED_CAP <= 0xFF, class_cap_fits_jid8);\n")
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
    """Write `content` to `path` only when it differs from what is there.

    The pre-existing-content read is purely a change-detection optimization
    (skip the write when the file already matches). An on-disk file that is
    missing, unreadable, or not valid UTF-8 (a corrupt/partial ACTIVE surface
    is exactly the case active-heal exists to repair) must not block the
    *actual* write: it is treated as "differs" and we fall through to writing
    the correct content. This is deliberately narrower than swallowing all
    write errors -- the write itself is never guarded, so a genuine write
    failure (permission denied, read-only filesystem, disk full) still
    raises straight out to the caller instead of being masked into a false
    success.
    """
    existing = None
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                existing = handle.read()
        except (OSError, UnicodeDecodeError):
            existing = None
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


def _active_outputs(out_dir=None, env=None):
    """The three build-local ACTIVE surfaces (machine, human, C header)."""
    out_dir = out_dir or ACTIVE_OUT_DIR
    return [
        (os.path.join(out_dir, ACTIVE_HEADER_NAME), render_active_header(env)),
        (os.path.join(out_dir, ACTIVE_JSON_NAME), render_active_json(env)),
        (os.path.join(out_dir, ACTIVE_MD_NAME), render_active_markdown(env)),
    ]


def cmd_generate(_args):
    validate_all_configured_caps()
    for path, content in _outputs():
        changed = write_if_changed(path, content)
        rel = os.path.relpath(path, REPO_ROOT)
        print("{} {}".format("wrote" if changed else "up-to-date", rel))
    return 0


def _write_active_surfaces(out_dir, env=None):
    """Render (census included) + write-if-changed the three ACTIVE surfaces.

    Shared by `active-generate` and by the `active-heal` regen leg, so both
    write byte-identical files and both loudly propagate any cap/schema/IO
    error (validate_all_configured_caps / validate_active_contract raise, the
    table loaders raise) instead of swallowing it.
    """
    validate_all_configured_caps()
    payload = active_contract(env)
    validate_active_contract(payload)
    for path, content in _active_outputs(out_dir, env):
        changed = write_if_changed(path, content)
        rel = os.path.relpath(path, REPO_ROOT)
        print("{} {}".format("wrote" if changed else "up-to-date", rel))
    item = [d for d in payload["domains"] if d["key"] == "item"][0]
    print("active item contract: cap 0x{:02X}, {} record(s) "
          "(default cap 0x{:02X}, {} record(s))".format(
              item["active_configured_cap"], item["active_record_count"],
              item["default_cap"], item["default_record_count"]))
    return payload


def cmd_active_generate(args):
    """Write the build-local ACTIVE surfaces (never a committed file)."""
    _write_active_surfaces(getattr(args, "out_dir", None))
    return 0


# --------------------------------------------------------------------------
# Cheap ACTIVE self-heal probe (no consumer census / source walk)
# --------------------------------------------------------------------------
# The ACTIVE surfaces are a FORCE prerequisite of the generated table, so their
# heal recipe runs on *every* build. Re-rendering them means the full
# consumer_census source walk (~15 MB, ~8-11 s) even for a warm, already-correct
# build -- a fixed per-build tax on a no-op. `active-heal` replaces that with a
# sub-second probe: it computes ONLY the census-free cap/record-count model
# (_active_domain_entries) and compares it against the metadata already on disk.
# If every surface already agrees (the warm no-op) it writes nothing and returns
# -- no census, no mtime change, no rebuild storm. Only when a surface is
# missing, unparseable, schema-outdated, or reports a stale cap/count does it
# fall through to one full active render (census included). Source/classification
# drift stays owned by the grouped rule's ordinary Make prerequisites; this probe
# owns only the cheap "is what's on disk still true for THIS resolved cap" question.

_HDR_DEFINE_RE = re.compile(
    r"^#define\s+(?P<name>[A-Z0-9_]+)\s+(?P<val>0[xX][0-9A-Fa-f]+|-?\d+)\s*$",
    re.MULTILINE,
)


def _parse_active_header_defines(text):
    """Macro name -> int for every simple `#define NAME <intlit>` in a header."""
    out = {}
    for m in _HDR_DEFINE_RE.finditer(text):
        out[m.group("name")] = int(m.group("val"), 0)
    return out


def _expected_active_summary(env=None):
    """Cheap ({key: entry}, item_entry) census-free expectation for THIS build."""
    domains, _caps, _counts = _active_domain_entries(env)
    by_key = {d["key"]: d for d in domains}
    return by_key, by_key["item"]


def active_heal_reasons(out_dir=None, env=None):
    """Reasons the on-disk ACTIVE surfaces are stale for THIS resolved build.

    Returns an empty list when every surface already matches the census-free
    model (the warm no-op path). A non-empty list means a full regen is due.
    A missing/unparseable/mismatched *on-disk* surface is a heal reason (not an
    error); errors from computing the expectation itself (bad cap, schema/IO
    failure loading a record table) propagate loudly to the caller.
    """
    out_dir = out_dir or ACTIVE_OUT_DIR
    expected, _item = _expected_active_summary(env)
    reasons = []

    header_path = os.path.join(out_dir, ACTIVE_HEADER_NAME)
    json_path = os.path.join(out_dir, ACTIVE_JSON_NAME)
    md_path = os.path.join(out_dir, ACTIVE_MD_NAME)
    for path in (header_path, json_path, md_path):
        if not os.path.exists(path):
            reasons.append("missing: {}".format(os.path.relpath(path, REPO_ROOT)))
    if reasons:
        return reasons

    # --- ACTIVE C header (the compile-authoritative surface) ---------------
    try:
        with open(header_path, "r", encoding="utf-8") as handle:
            defines = _parse_active_header_defines(handle.read())
    except (OSError, UnicodeDecodeError) as exc:
        reasons.append("unparseable: {} ({})".format(ACTIVE_HEADER_NAME, exc))
        defines = None
    if defines is not None:
        for key, d in expected.items():
            macro = key.upper()
            checks = [
                (macro + "_ID_DEFAULT_CAP", d["default_cap"]),
                (macro + "_ID_ACTIVE_CONFIGURED_CAP", d["active_configured_cap"]),
                (macro + "_ID_ACTIVE_EXPANDED", 1 if d["expanded_past_default"] else 0),
            ]
            if d["record_count_status"] == "counted":
                checks.append((macro + "_ID_DEFAULT_RECORD_COUNT", d["default_record_count"]))
                checks.append((macro + "_ID_ACTIVE_RECORD_COUNT", d["active_record_count"]))
            for name, want in checks:
                got = defines.get(name)
                if got != want:
                    reasons.append(
                        "header {}: {} = {} (expected {})".format(
                            ACTIVE_HEADER_NAME, name, got, want))

    # --- ACTIVE JSON (schema version + machine cap/count model) ------------
    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except (ValueError, OSError) as exc:
        reasons.append("unparseable: {} ({})".format(ACTIVE_JSON_NAME, exc))
        doc = None
    if doc is not None:
        if doc.get("schema_version") != SCHEMA_VERSION:
            reasons.append(
                "json {}: schema_version {} (expected {})".format(
                    ACTIVE_JSON_NAME, doc.get("schema_version"), SCHEMA_VERSION))
        json_by_key = {d.get("key"): d for d in doc.get("domains", [])}
        for key, d in expected.items():
            jd = json_by_key.get(key)
            if jd is None:
                reasons.append("json {}: missing domain {}".format(ACTIVE_JSON_NAME, key))
                continue
            for field in ("default_cap", "active_configured_cap",
                          "default_record_count", "active_record_count"):
                if jd.get(field) != d[field]:
                    reasons.append(
                        "json {}: {}.{} = {} (expected {})".format(
                            ACTIVE_JSON_NAME, key, field, jd.get(field), d[field]))

    # --- ACTIVE Markdown (human table -- verify the volatile cap/count row) -
    try:
        with open(md_path, "r", encoding="utf-8") as handle:
            md_text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        reasons.append("unparseable: {} ({})".format(ACTIVE_MD_NAME, exc))
        md_text = None
    if md_text is not None:
        for key, d in expected.items():
            if d["record_count_status"] != "counted":
                continue
            # The domains table renders one row per domain:
            #   | item | 0xCD | 206 | 0xCD | 206 | no | `items` table |
            want_cells = "| {} | {} | {} | {} | {} | {} |".format(
                key, d["default_cap_hex"], d["default_record_count"],
                d["active_configured_cap_hex"], d["active_record_count"],
                "yes" if d["expanded_past_default"] else "no")
            if want_cells not in md_text:
                reasons.append(
                    "md {}: no current row for domain {} (expected cap {} / {} record(s))".format(
                        ACTIVE_MD_NAME, key, d["active_configured_cap_hex"],
                        d["active_record_count"]))

    return reasons


def cmd_active_heal(args):
    """Cheap probe; regenerate the ACTIVE surfaces once only when stale.

    Warm, already-correct builds return without touching the census or any file
    (mtime preserved -- no rebuild storm). Missing/stale/cap-count-mismatched
    surfaces fall through to a single full render. Cap/schema/IO errors are not
    swallowed: they raise straight out (no exit-1 mask, no `|| true`).
    """
    out_dir = getattr(args, "out_dir", None)
    reasons = active_heal_reasons(out_dir)
    if not reasons:
        _by_key, item = _expected_active_summary()
        print("active id-space contract current (cheap probe, no regen); "
              "item cap 0x{:02X}, {} record(s)".format(
                  item["active_configured_cap"], item["active_record_count"]))
        return 0
    print("active id-space contract stale -- regenerating ({} reason(s)):".format(
        len(reasons)))
    for reason in reasons:
        print("  - {}".format(reason))
    _write_active_surfaces(out_dir)
    return 0


def cmd_active_check(args):
    """Self-heal the build-local ACTIVE surfaces and prove they are current.

    These outputs live only under build/, so there is no committed file to
    drift against: like the manifest C header, `check` regenerates them
    write-if-changed (so a cap flip or an out-of-band edit heals) and then
    re-reads them to prove what is on disk is exactly what the model renders.
    """
    validate_all_configured_caps()
    payload = active_contract()
    validate_active_contract(payload)
    out_dir = getattr(args, "out_dir", None)
    outputs = _active_outputs(out_dir)
    for path, content in outputs:
        write_if_changed(path, content)
    stale = []
    for path, content in outputs:
        with open(path, "r", encoding="utf-8") as handle:
            if handle.read() != content:
                stale.append(os.path.relpath(path, REPO_ROOT))
    if stale:
        for rel in stale:
            print("stale active output: {}".format(rel), file=sys.stderr)
        return 1
    item = [d for d in payload["domains"] if d["key"] == "item"][0]
    print("active id-space contract up-to-date ({} outputs); item cap 0x{:02X}, "
          "{} record(s)".format(len(outputs), item["active_configured_cap"],
                                item["active_record_count"]))
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
    act = sub.add_parser("active-generate",
                         help="write the build-local ACTIVE cap/count contract "
                              "(JSON + Markdown + C header) for this build")
    act.add_argument("--out-dir", help="output directory (default: build/generated/data)")
    act.set_defaults(func=cmd_active_generate)
    act_heal = sub.add_parser(
        "active-heal",
        help="cheap probe: regenerate the build-local ACTIVE contract only when "
             "a surface is missing/stale for the resolved cap (no source walk on "
             "a warm no-op)")
    act_heal.add_argument("--out-dir", help="output directory (default: build/generated/data)")
    act_heal.set_defaults(func=cmd_active_heal)
    act_chk = sub.add_parser("active-check",
                             help="self-heal + verify the build-local ACTIVE contract")
    act_chk.add_argument("--out-dir", help="output directory (default: build/generated/data)")
    act_chk.set_defaults(func=cmd_active_check)
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
