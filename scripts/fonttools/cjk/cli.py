"""Command-line entry point for deterministic CJK font assets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bootstrap import bootstrap_fonts
from .inventory import (
    CjkFontError,
    LOCALES,
    check_generated_files,
    scalar_text,
    write_generated_files,
)
from .package import (
    GATE_REPORT,
    GENERATION_REPORT,
    PACKAGE_ARCHIVE,
    archive_package,
    check_compact_assets,
    record_gate_evidence,
    write_compact_assets,
)


def _root(value: str) -> Path:
    return Path(value).resolve()


def _generate_inventory(args: argparse.Namespace) -> int:
    generated = write_generated_files(args.root)
    inventory = generated["fonts/cjk/inventory.json"]
    print(
        f"generated deterministic CJK inventory: {len(generated)} files, "
        f"inventory_bytes={len(inventory)}"
    )
    return 0


def _bootstrap(args: argparse.Namespace) -> int:
    downloaded = bootstrap_fonts(args.root)
    print(
        "verified pinned Noto bootstrap inputs: "
        f"downloaded={downloaded} cached={3 - downloaded}"
    )
    return 0


def _archive(args: argparse.Namespace) -> int:
    data = archive_package(args.package_dir, args.output)
    print(f"archived FEBuilder package: {args.output} ({len(data)} bytes)")
    return 0


def _import(args: argparse.Namespace) -> int:
    outputs = write_compact_assets(args.root, args.package, args.report)
    manifest = outputs["graphics/fonts/cjk/manifest.json"]
    print(
        f"imported deterministic CJK font assets: {len(outputs) - 1} binaries, "
        f"manifest_bytes={len(manifest)}"
    )
    return 0


def _record_gates(args: argparse.Namespace) -> int:
    evidence = record_gate_evidence(
        args.root,
        args.dry_run_report,
        args.generation_report,
        args.output_report,
        args.gate_report,
        cli_command=args.cli_command,
        commit=args.commit,
        dotnet_sdk=args.dotnet_sdk,
        repository=args.repository,
    )
    print(
        "recorded FEBuilder gate evidence: "
        f"jobs={evidence['gates']['generate']['job_count']} "
        f"rows={evidence['gates']['generate']['row_count']} "
        f"output={args.gate_report}"
    )
    return 0


def _check(args: argparse.Namespace) -> int:
    inventory = check_generated_files(args.root)
    assets = check_compact_assets(args.root)
    inventory_document = json.loads(
        inventory["fonts/cjk/inventory.json"].decode("utf-8")
    )
    coverage = ",".join(
        f"{locale}:{inventory_document['locales'][locale]['glyph_scalar_count']}"
        f"x{len(inventory_document['locales'][locale]['styles'])}"
        for locale in LOCALES
    )
    review_scalars = []
    for scalar in (0x5019, 0x8A3A, 0x8BCA):
        locales = [
            locale
            for locale in LOCALES
            if chr(scalar)
            in inventory[f"fonts/cjk/corpora/{locale}.system.txt"].decode("utf-8")
        ]
        if not locales:
            raise CjkFontError(f"{scalar_text(scalar)} is not covered")
        review_scalars.append(f"{scalar_text(scalar)}:{'+'.join(locales)}")
    print(
        "CJK font assets verified: "
        f"inventory_files={len(inventory)} aggregate_files={len(assets)} "
        f"coverage={coverage} "
        f"union={inventory_document['union']['glyph_scalar_count']} "
        "all_catalog_and_game_scalars=covered "
        f"review_scalars={','.join(review_scalars)}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=_root, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser(
        "generate-inventory",
        help="write deterministic corpora, maps, provenance, and FEBuilder manifest",
    )
    inventory.set_defaults(handler=_generate_inventory)

    bootstrap = subparsers.add_parser(
        "bootstrap-fonts",
        help="explicitly fetch missing Noto inputs from immutable hash-pinned URLs",
    )
    bootstrap.set_defaults(handler=_bootstrap)

    archive = subparsers.add_parser(
        "archive-package",
        help="pack a validated FEBuilder directory into a deterministic ZIP",
    )
    archive.add_argument("--package-dir", type=Path, required=True)
    archive.add_argument(
        "--output",
        type=Path,
        default=Path(PACKAGE_ARCHIVE),
    )
    archive.set_defaults(handler=_archive)

    importer = subparsers.add_parser(
        "import-package",
        help="import a validated FEBuilder package into compact aggregate assets",
    )
    importer.add_argument("--package", type=Path, required=True)
    importer.add_argument("--report", type=Path, required=True)
    importer.set_defaults(handler=_import)

    gates = subparsers.add_parser(
        "record-gates",
        help="record passing temporary FEBuilder gates and commit-safe reports",
    )
    gates.add_argument("--dry-run-report", type=Path, required=True)
    gates.add_argument("--generation-report", type=Path, required=True)
    gates.add_argument(
        "--output-report",
        type=Path,
        default=Path(GENERATION_REPORT),
    )
    gates.add_argument(
        "--gate-report",
        type=Path,
        default=Path(GATE_REPORT),
    )
    gates.add_argument("--cli-command", required=True)
    gates.add_argument("--commit", required=True)
    gates.add_argument("--dotnet-sdk", required=True)
    gates.add_argument("--repository", required=True)
    gates.set_defaults(handler=_record_gates)

    check = subparsers.add_parser(
        "check",
        help="verify inventory, gate evidence, compact assets, hashes, and coverage",
    )
    check.set_defaults(handler=_check)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (CjkFontError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
