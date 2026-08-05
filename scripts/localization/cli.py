"""CLI entry point for the expansion localization platform (issue #18).
Stdlib argparse only, matching scripts/modernize/*.py's own convention.

Subcommands:
  validate  -- load + fully validate the registry/catalog; silent on
               success, exits 1 with an actionable message otherwise.
  generate  -- validate, then write the generated C header/source +
               budget report under --out-dir (always under build/).
  check     -- CI-suitable gate: validate + generate (self-heals the
               generated files under --out-dir; never touches anything
               committed).
  budget    -- validate + generate, then print the budget report JSON to
               stdout (in addition to writing it to --out-dir).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import DEFAULT_REGISTRY_PATH, load_catalog
from .generate import generate as generate_impl
from .schema import SchemaError


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument(
        "--catalog",
        action="append",
        default=None,
        metavar="LOCALE=PATH",
        help=(
            "authored catalog mapping; repeat per locale. If omitted, uses "
            "the repository en/ja/zh-Hans catalogs"
        ),
    )


def _catalog_paths(values):
    if values is None:
        return None
    result = {}
    for value in values:
        locale, separator, path = value.partition("=")
        if not separator or not locale or not path:
            raise SchemaError(
                f"invalid --catalog {value!r}; expected a stable LOCALE=PATH mapping"
            )
        if locale in result:
            raise SchemaError(f"duplicate --catalog mapping for locale {locale!r}")
        result[locale] = Path(path)
    return result


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--budget-json", type=Path, default=None)


def cmd_validate(args: argparse.Namespace) -> int:
    load_catalog(registry_path=args.registry, catalog_paths=_catalog_paths(args.catalog))
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    generate_impl(
        output_dir=args.out_dir,
        budget_json_path=args.budget_json,
        registry_path=args.registry,
        catalog_paths=_catalog_paths(args.catalog),
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    return cmd_generate(args)


def cmd_budget(args: argparse.Namespace) -> int:
    written = generate_impl(
        output_dir=args.out_dir,
        budget_json_path=args.budget_json,
        registry_path=args.registry,
        catalog_paths=_catalog_paths(args.catalog),
    )
    print(written["budget_json"].read_text(encoding="utf-8"), end="")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_p = sub.add_parser("validate", help="validate the registry/catalog; silent on success")
    _add_source_args(validate_p)

    generate_p = sub.add_parser("generate", help="validate, then write generated files")
    _add_source_args(generate_p)
    _add_output_args(generate_p)

    check_p = sub.add_parser("check", help="CI gate: validate + generate (self-heals build/ output)")
    _add_source_args(check_p)
    _add_output_args(check_p)

    budget_p = sub.add_parser("budget", help="validate + generate, then print the budget report")
    _add_source_args(budget_p)
    _add_output_args(budget_p)

    args = parser.parse_args(argv)

    handlers = {
        "validate": cmd_validate,
        "generate": cmd_generate,
        "check": cmd_check,
        "budget": cmd_budget,
    }

    try:
        return handlers[args.command](args)
    except SchemaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
