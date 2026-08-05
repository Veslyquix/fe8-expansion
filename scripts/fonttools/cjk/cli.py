"""Command-line entry point for deterministic CJK font assets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bootstrap import bootstrap_fonts
from .inventory import (
    CjkFontError,
    check_generated_files,
    write_generated_files,
)
from .package import (
    PACKAGE_ARCHIVE,
    archive_package,
    check_compact_assets,
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


def _check(args: argparse.Namespace) -> int:
    inventory = check_generated_files(args.root)
    assets = check_compact_assets(args.root)
    print(
        "CJK font assets verified: "
        f"inventory_files={len(inventory)} aggregate_files={len(assets)} "
        "coverage=ja:1846x2,zh-Hans:2459x2 union=3329 "
        "source_non_ascii_union=3330 spacing=1"
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

    check = subparsers.add_parser(
        "check",
        help="verify inventory, package import, compact assets, hashes, and coverage",
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
