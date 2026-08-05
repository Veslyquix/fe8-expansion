"""CLI for deterministic full-game localized catalog generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import (
    DEFAULT_JA_INDEXED_PATH,
    DEFAULT_MAPPING_PATH,
    DEFAULT_TARGET_HEADER_PATH,
    DEFAULT_ZH_INDEXED_PATH,
    DEFAULT_ZH_RAW_PATH,
    GameCatalogError,
    build_game_catalog,
    write_build,
)


def _locale_path_map(values):
    if values is None:
        return None
    result = {}
    for value in values:
        locale, separator, path = value.partition("=")
        if not separator or not locale or not path:
            raise GameCatalogError(f"invalid locale mapping {value!r}; expected LOCALE=PATH")
        if locale in result:
            raise GameCatalogError(f"duplicate locale mapping for {locale!r}")
        result[locale] = Path(path)
    return result


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ja-indexed", type=Path, default=DEFAULT_JA_INDEXED_PATH)
    parser.add_argument("--zh-indexed", type=Path, default=DEFAULT_ZH_INDEXED_PATH)
    parser.add_argument("--zh-raw", type=Path, default=DEFAULT_ZH_RAW_PATH)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING_PATH)
    parser.add_argument("--target-header", type=Path, default=DEFAULT_TARGET_HEADER_PATH)
    parser.add_argument(
        "--authored",
        action="append",
        default=None,
        metavar="LOCALE=PATH",
        help="optional authored translation source per locale",
    )
    parser.add_argument(
        "--no-suffix-share",
        action="store_true",
        help="disable immediate-predecessor compressed suffix sharing",
    )


def _suffix_share(args: argparse.Namespace) -> bool:
    return not args.no_suffix_share


def _build_summary(build) -> str:
    mapping = build.report["mapping_source_counts"]
    ja = build.report["locales"]["ja"]
    zh = build.report["locales"]["zh-Hans"]
    return (
        "targets={targets} indexed={indexed} raw={raw} authored={authored} "
        "fallback={fallback} unresolved={unresolved} "
        "ja.present={ja_present} zh.present={zh_present}"
    ).format(
        targets=build.target_count,
        indexed=mapping["indexed"],
        raw=mapping["raw"],
        authored=mapping["authored"],
        fallback=mapping["english_fallback"],
        unresolved=mapping["unresolved"],
        ja_present=ja["present_count"],
        zh_present=zh["present_count"],
    )


def _build_from_args(args: argparse.Namespace):
    return build_game_catalog(
        ja_indexed_path=args.ja_indexed,
        zh_indexed_path=args.zh_indexed,
        zh_raw_path=args.zh_raw,
        mapping_path=args.mapping,
        target_header_path=args.target_header,
        authored_paths=_locale_path_map(args.authored),
        suffix_share=_suffix_share(args),
    )


def cmd_validate(args: argparse.Namespace) -> int:
    build = _build_from_args(args)
    print("validated full-game locale catalog inputs: " + _build_summary(build))
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    build = _build_from_args(args)
    write_build(build, output_dir=args.out_dir)
    print(
        "generated full-game locale catalog into {out_dir}: {summary}".format(
            out_dir=args.out_dir,
            summary=_build_summary(build),
        )
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    return cmd_generate(args)


def cmd_budget(args: argparse.Namespace) -> int:
    build = _build_from_args(args)
    write_build(build, output_dir=args.out_dir)
    print(json.dumps(build.budget, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_p = sub.add_parser("validate", help="validate inputs and in-memory catalogs")
    _add_common_args(validate_p)
    validate_p.set_defaults(handler=cmd_validate)

    for command, handler, help_text in (
        ("generate", cmd_generate, "generate header/source/report/budget under --out-dir"),
        ("check", cmd_check, "CI-suitable alias for generate"),
        ("budget", cmd_budget, "generate outputs and print the budget JSON"),
    ):
        sub_parser = sub.add_parser(command, help=help_text)
        _add_common_args(sub_parser)
        sub_parser.add_argument("--out-dir", type=Path, required=True)
        sub_parser.set_defaults(handler=handler)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (GameCatalogError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
