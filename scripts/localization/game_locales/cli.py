"""Command-line tools for importing and auditing full-game locale sources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .coverage import build_coverage_report, load_fe8u_target_ids
from .importer import import_locale_sources
from .mapping import MappingError, validate_mapping_document
from .parsers import LocaleSourceError


def _load_mapping(path: Path, target_count: int):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MappingError(f"{path}: invalid JSON: {error}") from error
    return validate_mapping_document(data, target_count=target_count)


def _cmd_import(args: argparse.Namespace) -> int:
    written = import_locale_sources(
        jp_text_path=args.jp_text,
        jp_controls_path=args.jp_controls,
        cn_text_path=args.cn_text,
        mapping_seed_path=args.mapping_seed,
        output_dir=args.out_dir,
    )
    manifest = json.loads(written["manifest.json"].read_text(encoding="utf-8"))
    print(
        "imported "
        f"JP={manifest['locales']['ja']['indexed']['message_count']} "
        f"CN-indexed={manifest['locales']['zh-Hans']['indexed']['message_count']} "
        f"CN-raw={manifest['locales']['zh-Hans']['raw']['record_count']}/"
        f"{manifest['locales']['zh-Hans']['raw']['unique_address_count']} "
        f"into {args.out_dir}"
    )
    return 0


def _cmd_validate_mapping(args: argparse.Namespace) -> int:
    target_ids = load_fe8u_target_ids(args.target_header)
    mapping = _load_mapping(args.mapping, len(target_ids))
    print(
        f"valid {mapping.authority} mapping: {len(mapping.rows)} rows, "
        f"locale_ids={','.join(mapping.locale_ids)}"
    )
    return 0


def _cmd_coverage(args: argparse.Namespace) -> int:
    target_ids = load_fe8u_target_ids(args.target_header)
    mapping = _load_mapping(args.mapping, len(target_ids))
    report = build_coverage_report(mapping, target_ids, locale=args.locale)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser(
        "import",
        help="import the four pinned locale inputs into deterministic artifacts",
    )
    import_parser.add_argument("--jp-text", type=Path, required=True)
    import_parser.add_argument("--jp-controls", type=Path, required=True)
    import_parser.add_argument("--cn-text", type=Path, required=True)
    import_parser.add_argument("--mapping-seed", type=Path, required=True)
    import_parser.add_argument("--out-dir", type=Path, required=True)
    import_parser.set_defaults(handler=_cmd_import)

    validate_parser = subparsers.add_parser(
        "validate-mapping",
        help="validate sparse mapping syntax and candidate/verified authority semantics",
    )
    validate_parser.add_argument("--mapping", type=Path, required=True)
    validate_parser.add_argument(
        "--target-header",
        type=Path,
        default=Path("include/constants/msg.h"),
    )
    validate_parser.set_defaults(handler=_cmd_validate_mapping)

    coverage_parser = subparsers.add_parser(
        "coverage",
        help="classify every FE8U target using an authority-gated sparse mapping",
    )
    coverage_parser.add_argument("--mapping", type=Path, required=True)
    coverage_parser.add_argument("--locale", choices=("ja", "zh-Hans"), required=True)
    coverage_parser.add_argument(
        "--target-header",
        type=Path,
        default=Path("include/constants/msg.h"),
    )
    coverage_parser.set_defaults(handler=_cmd_coverage)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (LocaleSourceError, MappingError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
