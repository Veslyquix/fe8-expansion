"""Command-line entry point: ``python3 -m scripts.generated_data <command> ...``

Commands:

* ``validate`` -- load + validate a table's JSON source; report every
  diagnostic (not just the first) with ``file:line:column`` locations.
* ``generate`` -- validate, then write C89 output under ``build/generated/data``
  (write-if-changed), the committed inventory/summary report, and (for
  tables that have one) run the hand-written round-trip comparison.
* ``content-text`` -- issue #6: write the build-local, content-profile-only
  authored item text (a C89 header consumed by
  ``src/expansion_starter_content.c`` plus an audit catalog). Writes nothing
  when ``EXPANSION_STARTER_CONTENT`` is 0, so a default build links no
  content string at all.
* ``check`` -- like ``generate``, self-healing the ephemeral ``build/``
  output (write-if-changed, exactly like ``generate``), but never writing
  the committed inventory: it only compares against what's on disk and
  reports drift (with a non-zero exit) if the committed inventory,
  validation, or hand-written round-trip has gone stale. Suitable for
  CI/pre-commit use.

Every table is driven exclusively through the :class:`~.schema.TableSchema`
interface (``registry.py`` registers one instance per table) -- there is no
per-table ``if table == "...":`` dispatch here. A table that has nothing to
generate (metadata-only, e.g. ``eventscripts``) simply leaves
``default_output_name`` (and ``generate_c``) as ``None``; ``generate``/
``check`` detect that and explicitly skip writing C instead of emitting a
meaningless file.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import registry  # noqa: F401  (import registers table schemas)
from . import manifest as manifest_mod
from .cgen import write_if_changed
from .diagnostics import GeneratedDataError, DiagnosticCollector
from .schema import REGISTRY

DEFAULT_OUT_DIR = os.path.join("build", "generated", "data")
DEFAULT_MANIFEST_REPORT = os.path.join("reports", "generated_data_manifest.md")
MANIFEST_HEADER_NAME = "generated_data_manifest.h"


def _resolve_schema(table):
    return REGISTRY.resolve(table)


def _parse_dep_source_overrides(raw_pairs):
    """Parse repeated ``--dep-source NAME=PATH`` options into a ``dict``."""
    overrides = {}
    for pair in raw_pairs or ():
        if "=" not in pair:
            raise GeneratedDataError("--dep-source expects NAME=PATH, got '{}'".format(pair))
        name, path = pair.split("=", 1)
        overrides[name] = path
    return overrides


def _load_dependency_records(schema, dep_source_overrides):
    """Load this schema's declared ``dependency_tables()`` deterministically
    (in declaration order) through the schema registry, returning ``None``
    when the table has no table-level dependencies (so callers can fall
    back to the plain 2-argument ``validate`` signature unchanged)."""
    dep_tables = tuple(schema.dependency_tables())
    if not dep_tables:
        return None
    dependency_records = {}
    for dep_name in dep_tables:
        dep_schema = REGISTRY.resolve(dep_name)
        dep_source = dep_source_overrides.get(dep_name) or dep_schema.default_source
        dependency_records[dep_name] = dep_schema.load_records(dep_source)
    return dependency_records


def _load_and_validate(schema, source_path, dep_source_overrides=None):
    records = schema.load_records(source_path)
    diagnostics = DiagnosticCollector()
    dependency_records = _load_dependency_records(schema, dep_source_overrides or {})
    if dependency_records is not None:
        schema.validate(records, diagnostics, dependency_records)
    else:
        schema.validate(records, diagnostics)
    return records, diagnostics


def _roundtrip_errors(schema, records, hand_source, no_roundtrip):
    if no_roundtrip or not hand_source:
        return []
    if not os.path.exists(hand_source):
        return []
    return schema.round_trip_errors(records, hand_source)


def cmd_validate(args):
    table = args.table
    try:
        schema = _resolve_schema(table)
    except GeneratedDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    source_path = args.source or schema.default_source
    try:
        dep_source_overrides = _parse_dep_source_overrides(args.dep_source)
        records, diagnostics = _load_and_validate(schema, source_path, dep_source_overrides)
    except GeneratedDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    hand_source = args.hand_source or schema.default_hand_source
    roundtrip_errors = []
    try:
        roundtrip_errors = _roundtrip_errors(schema, records, hand_source, args.no_roundtrip)
    except GeneratedDataError as exc:
        roundtrip_errors = [exc]

    all_errors = list(diagnostics.errors) + roundtrip_errors
    if all_errors:
        for error in all_errors:
            print(str(error), file=sys.stderr)
        print("FAILED: {} diagnostic(s)".format(len(all_errors)), file=sys.stderr)
        return 1

    print("OK: {} record(s) in {} validated against schema '{}'".format(len(records), source_path, schema.name))
    return 0


def cmd_generate(args):
    table = args.table
    try:
        schema = _resolve_schema(table)
    except GeneratedDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    source_path = args.source or schema.default_source
    out_dir = args.out_dir or DEFAULT_OUT_DIR
    inventory_path = args.inventory or schema.default_inventory_path
    hand_source = args.hand_source or schema.default_hand_source

    try:
        dep_source_overrides = _parse_dep_source_overrides(args.dep_source)
        records, diagnostics = _load_and_validate(schema, source_path, dep_source_overrides)
    except GeneratedDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    roundtrip_errors = []
    try:
        roundtrip_errors = _roundtrip_errors(schema, records, hand_source, args.no_roundtrip)
    except GeneratedDataError as exc:
        roundtrip_errors = [exc]

    all_errors = list(diagnostics.errors) + roundtrip_errors
    if all_errors:
        for error in all_errors:
            print(str(error), file=sys.stderr)
        print("FAILED: {} diagnostic(s); nothing written".format(len(all_errors)), file=sys.stderr)
        return 1

    if schema.default_output_name:
        output_path = os.path.join(out_dir, schema.default_output_name)
        content = schema.generate_c(records, source_path)
        if content is None:
            raise GeneratedDataError(
                "schema '{}' declares an output name but generate_c() returned None".format(table)
            )
        changed = write_if_changed(output_path, content)
        print("{} {}".format("wrote" if changed else "up to date:", output_path))
    else:
        print("skip: table '{}' is metadata-only; no C output generated".format(table))

    if inventory_path:
        inventory_content = schema.build_inventory(records)
        inventory_changed = write_if_changed(inventory_path, inventory_content)
        print("{} {}".format("wrote" if inventory_changed else "up to date:", inventory_path))

    return 0


def cmd_check(args):
    """Fail on drift in committed artifacts (inventory); self-heals the
    ephemeral build/ output but never touches anything outside build/.
    """
    table = args.table
    try:
        schema = _resolve_schema(table)
    except GeneratedDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    source_path = args.source or schema.default_source
    out_dir = args.out_dir or DEFAULT_OUT_DIR
    inventory_path = args.inventory or schema.default_inventory_path
    hand_source = args.hand_source or schema.default_hand_source

    try:
        dep_source_overrides = _parse_dep_source_overrides(args.dep_source)
        records, diagnostics = _load_and_validate(schema, source_path, dep_source_overrides)
    except GeneratedDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    roundtrip_errors = []
    try:
        roundtrip_errors = _roundtrip_errors(schema, records, hand_source, args.no_roundtrip)
    except GeneratedDataError as exc:
        roundtrip_errors = [exc]

    all_errors = list(diagnostics.errors) + roundtrip_errors
    if all_errors:
        for error in all_errors:
            print(str(error), file=sys.stderr)
        print("FAILED: {} diagnostic(s)".format(len(all_errors)), file=sys.stderr)
        return 1

    drift_found = False

    # The bulky C output lives only under build/ and is never committed, so
    # there is nothing to "drift" against across git history -- regenerate
    # it (write-if-changed) exactly like `generate` would, purely so
    # incremental `make` builds stay current. Metadata-only tables (no
    # default_output_name) have nothing to (re)generate here.
    if schema.default_output_name:
        output_path = os.path.join(out_dir, schema.default_output_name)
        generated_content = schema.generate_c(records, source_path)
        if generated_content is not None:
            write_if_changed(output_path, generated_content)

    if inventory_path:
        generated_inventory = schema.build_inventory(records)
        existing_inventory = None
        if os.path.exists(inventory_path):
            with open(inventory_path, "r", encoding="utf-8") as handle:
                existing_inventory = handle.read()
        if existing_inventory != generated_inventory:
            print(
                "DRIFT: committed inventory {} is stale (regenerate with `generate`)".format(inventory_path),
                file=sys.stderr,
            )
            drift_found = True

    if drift_found:
        return 1

    print("OK: no drift for table '{}' ({} record(s))".format(table, len(records)))
    return 0


def cmd_manifest(args):
    """Aggregate public registry/counts/dependency surface across every
    registered table. Writes the committed Markdown manifest + the
    generated symbolic C header, and fails on any record-budget overflow.

    ``--check`` compares the committed manifest against a freshly built one
    (drift gate, writes nothing committed) but still self-heals the
    ephemeral build/ header, exactly like ``check`` does for per-table C.
    """
    out_dir = args.out_dir or DEFAULT_OUT_DIR
    report_path = args.report or DEFAULT_MANIFEST_REPORT

    try:
        entries = manifest_mod.collect_entries()
    except GeneratedDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    budget_errors = manifest_mod.budget_diagnostics(entries)
    if budget_errors:
        for error in budget_errors:
            print(str(error), file=sys.stderr)
        print("FAILED: {} record-budget diagnostic(s)".format(len(budget_errors)), file=sys.stderr)
        return 1

    report_content = manifest_mod.build_manifest_report(entries)
    header_content = manifest_mod.build_manifest_header(entries)
    header_path = os.path.join(out_dir, MANIFEST_HEADER_NAME)

    # The bulky/ephemeral C header always lives under build/ and is never
    # committed, so self-heal it write-if-changed under both modes.
    write_if_changed(header_path, header_content)

    if args.check:
        existing = None
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as handle:
                existing = handle.read()
        if existing != report_content:
            print(
                "DRIFT: committed manifest {} is stale (regenerate with `manifest`)".format(report_path),
                file=sys.stderr,
            )
            return 1
        print("OK: no manifest drift ({} table(s), {} record(s))".format(
            len(entries), sum(e.record_count for e in entries)))
        return 0

    report_changed = write_if_changed(report_path, report_content)
    print("{} {}".format("wrote" if report_changed else "up to date:", report_path))
    print("wrote (build) {}".format(header_path))
    return 0


def cmd_content_text(args):
    """Issue #6: emit the BUILD-LOCAL content text artifacts, and only in the
    content profile.

    Default profile (``EXPANSION_STARTER_CONTENT`` unset/0) writes nothing at
    all and removes any artifact a previous content build left behind, so a
    default build can never pick up a stale string table. Everything written
    lives under ``--out-dir`` (build/), is never committed, and is never
    hand-edited.
    """
    from .items import content_text as items_content_text
    from .items import schema as items_schema
    from . import idspace

    out_dir = args.out_dir or DEFAULT_OUT_DIR
    try:
        content = items_content_text.resolve_content_flag(args.content)
        paths = [os.path.join(out_dir, name)
                 for name in items_content_text.CONTENT_TEXT_ARTIFACTS]
        if not content:
            removed = [path for path in paths if os.path.exists(path)]
            for path in removed:
                os.remove(path)
            print("skip: EXPANSION_STARTER_CONTENT=0; no content text generated"
                  + (" (removed {} stale artifact(s))".format(len(removed)) if removed else ""))
            return 0

        cap = idspace.resolve_item_id_cap()
        items_content_text.require_cap(cap)

        source_path = args.source or items_schema.ITEMS_EXPANSION_SOURCE
        # Render the repo-relative path (never an absolute workspace path):
        # the generated artifacts must be byte-identical wherever the tree
        # is checked out.
        display_source = os.path.relpath(source_path, items_schema.REPO_ROOT)
        base_source = os.path.join(items_schema.REPO_ROOT, "src", "data", "items.json")
        records = items_schema.load_records(
            base_source, item_cap=cap, overlay_source=source_path)
        diagnostics = DiagnosticCollector()
        items_schema.validate(records, diagnostics, item_cap=cap,
                              expansion_header=items_schema.ITEMS_EXPANSION_HEADER)
        if diagnostics.errors:
            for error in diagnostics.errors:
                print(str(error), file=sys.stderr)
            print("FAILED: {} diagnostic(s); nothing written".format(
                len(diagnostics.errors)), file=sys.stderr)
            return 1

        collected = items_content_text.collect(records)
        if not collected:
            print("error: EXPANSION_STARTER_CONTENT=1 but no record in {} authors "
                  "content text (add an 'authoringName')".format(display_source),
                  file=sys.stderr)
            return 1

        header_path, catalog_path = paths
        header_changed = write_if_changed(
            header_path, items_content_text.render_header(collected, display_source))
        catalog_changed = write_if_changed(
            catalog_path, items_content_text.render_catalog(collected, display_source))
    except GeneratedDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("{} {} ({} authored content record(s))".format(
        "wrote" if header_changed else "up to date:", header_path, len(collected)))
    print("{} {}".format("wrote" if catalog_changed else "up to date:", catalog_path))
    return 0


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="python3 -m scripts.generated_data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_args(sub):
        sub.add_argument("--table", required=True, choices=REGISTRY.all_names() or ["supports"])
        sub.add_argument("--source", help="path to the table's JSON source (default: built-in per-table path)")
        sub.add_argument("--hand-source", help="path to the hand-written C file to round-trip against")
        sub.add_argument("--no-roundtrip", action="store_true", help="skip the hand-written round-trip comparison")
        sub.add_argument(
            "--dep-source", action="append",
            help="override a table dependency's JSON source as NAME=PATH (repeatable); "
                 "only meaningful for tables whose schema declares dependency_tables()",
        )

    validate_parser = subparsers.add_parser("validate", help="validate a table's JSON source")
    add_common_args(validate_parser)
    validate_parser.set_defaults(func=cmd_validate)

    generate_parser = subparsers.add_parser("generate", help="validate and generate C89 output + inventory")
    add_common_args(generate_parser)
    generate_parser.add_argument("--out-dir", help="output directory for generated C (default: build/generated/data)")
    generate_parser.add_argument("--inventory", help="path to the committed inventory/summary file to write")
    generate_parser.set_defaults(func=cmd_generate)

    check_parser = subparsers.add_parser("check", help="fail on validation or generation drift; writes nothing")
    add_common_args(check_parser)
    check_parser.add_argument("--out-dir", help="output directory to compare against (default: build/generated/data)")
    check_parser.add_argument("--inventory", help="path to the committed inventory/summary file to compare against")
    check_parser.set_defaults(func=cmd_check)

    manifest_parser = subparsers.add_parser(
        "manifest", help="build the aggregate public registry/counts/dependency surface")
    manifest_parser.add_argument(
        "--out-dir", help="output directory for the generated C header (default: build/generated/data)")
    manifest_parser.add_argument(
        "--report", help="path to the committed Markdown manifest (default: reports/generated_data_manifest.md)")
    manifest_parser.add_argument(
        "--check", action="store_true",
        help="fail on manifest drift or record-budget overflow; write nothing committed")
    manifest_parser.set_defaults(func=cmd_manifest)

    content_text_parser = subparsers.add_parser(
        "content-text",
        help="issue #6: emit the build-local, content-profile-only authored "
             "item text (header + audit catalog); a no-op at "
             "EXPANSION_STARTER_CONTENT=0")
    content_text_parser.add_argument(
        "--out-dir", help="output directory (default: build/generated/data)")
    content_text_parser.add_argument(
        "--source", help="path to the expansion overlay JSON "
                         "(default: src/data/items_expansion.json)")
    content_text_parser.add_argument(
        "--content", default=None,
        help="1 to generate the content text, 0 to generate nothing "
             "(default: the EXPANSION_STARTER_CONTENT environment value, else 0)")
    content_text_parser.set_defaults(func=cmd_content_text)

    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
