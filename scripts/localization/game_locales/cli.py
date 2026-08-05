"""Command-line tools for importing and auditing full-game locale sources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .coverage import build_coverage_report, load_fe8u_target_ids
from .crosswalk import (
    build_crosswalk_coverage_report,
    build_release_mapping,
    canonical_json_bytes,
    harvest_structural_evidence,
)
from .importer import (
    check_vendored_locale_sources,
    import_locale_sources,
    regenerate_vendored_locale_sources,
)
from .mapping import MappingError, validate_mapping_document
from .parsers import LocaleSourceError
from .raw_closure import (
    build_raw_surface_closure,
    canonical_json_bytes as closure_json_bytes,
)


def _load_mapping(path: Path, target_count: int):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MappingError(f"{path}: invalid JSON: {error}") from error
    return validate_mapping_document(data, target_count=target_count)


def _load_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MappingError(f"{path}: invalid JSON: {error}") from error


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
        f"{manifest['locales']['zh-Hans']['raw']['unique_import_count']} "
        f"into {args.out_dir}"
    )
    return 0


def _cmd_regenerate(args: argparse.Namespace) -> int:
    written = regenerate_vendored_locale_sources(
        source_dir=args.source_dir,
        output_dir=args.out_dir,
    )
    manifest = json.loads(written["manifest.json"].read_text(encoding="utf-8"))
    print(
        "regenerated committed locale artifacts "
        f"JP={manifest['locales']['ja']['indexed']['message_count']} "
        f"CN={manifest['locales']['zh-Hans']['indexed']['message_count']} "
        f"raw={manifest['locales']['zh-Hans']['raw']['record_count']}/"
        f"{manifest['locales']['zh-Hans']['raw']['unique_import_count']}"
    )
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    artifacts = check_vendored_locale_sources(
        source_dir=args.source_dir,
        output_dir=args.out_dir,
    )
    manifest = json.loads(artifacts["manifest.json"].decode("utf-8"))
    print(
        "locale artifacts match vendored raw snapshots byte-for-byte "
        f"JP={manifest['locales']['ja']['indexed']['message_count']} "
        f"CN={manifest['locales']['zh-Hans']['indexed']['message_count']} "
        f"raw={manifest['locales']['zh-Hans']['raw']['record_count']}/"
        f"{manifest['locales']['zh-Hans']['raw']['unique_import_count']}"
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


def _build_crosswalk_artifacts(args: argparse.Namespace):
    target_count = len(load_fe8u_target_ids(args.target_header))
    evidence = _load_json(args.evidence)
    candidates = _load_json(args.candidates)
    mapping = build_release_mapping(
        evidence,
        target_count=target_count,
        candidate_data=candidates,
    )
    report = build_crosswalk_coverage_report(mapping, target_count=target_count)
    return {
        args.mapping: canonical_json_bytes(mapping),
        args.report: canonical_json_bytes(report),
    }


def _cmd_harvest_crosswalk(args: argparse.Namespace) -> int:
    target_count = len(load_fe8u_target_ids(args.target_header))
    evidence = harvest_structural_evidence(
        fe8u_root=args.fe8u_root,
        fe8j_root=args.fe8j_root,
        raw_path=args.raw_source,
        target_count=target_count,
    )
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_bytes(canonical_json_bytes(evidence))
    print(
        f"harvested {len(evidence['records'])} structural evidence slots "
        f"with {len(evidence['gaps'])} explicit gaps"
    )
    return 0


def _cmd_build_crosswalk(args: argparse.Namespace) -> int:
    artifacts = _build_crosswalk_artifacts(args)
    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    mapping = json.loads(artifacts[args.mapping].decode("utf-8"))
    report = json.loads(artifacts[args.report].decode("utf-8"))
    print(
        f"built {len(mapping['rows'])} FE8U target decisions: "
        f"translated={report['translation_coverage']['count']} "
        f"fallback={report['explicit_fallback_coverage']['count']} "
        f"unresolved={report['unresolved_count']}"
    )
    return 0


def _cmd_check_crosswalk(args: argparse.Namespace) -> int:
    artifacts = _build_crosswalk_artifacts(args)
    mismatches = [
        str(path)
        for path, expected in artifacts.items()
        if not path.is_file() or path.read_bytes() != expected
    ]
    if mismatches:
        raise MappingError(
            "crosswalk artifacts differ from deterministic rebuild: "
            + ", ".join(mismatches)
        )
    mapping = json.loads(artifacts[args.mapping].decode("utf-8"))
    report = json.loads(artifacts[args.report].decode("utf-8"))
    print(
        f"crosswalk artifacts match committed bytes: decisions={len(mapping['rows'])} "
        f"translated={report['translation_coverage']['count']} "
        f"fallback={report['explicit_fallback_coverage']['count']} "
        f"unresolved={report['unresolved_count']}"
    )
    return 0


def _build_raw_closure(args: argparse.Namespace):
    return build_raw_surface_closure(
        raw_data=_load_json(args.raw_source),
        mapping_data=_load_json(args.mapping),
        decisions_data=_load_json(args.decisions),
        registry_data=_load_json(args.registry),
        catalog_data={
            "en": _load_json(args.catalog_en),
            "ja": _load_json(args.catalog_ja),
            "zh-Hans": _load_json(args.catalog_zh_hans),
        },
        repo_root=args.repo_root,
    )


def _cmd_build_raw_closure(args: argparse.Namespace) -> int:
    closure = _build_raw_closure(args)
    args.closure.parent.mkdir(parents=True, exist_ok=True)
    args.closure.write_bytes(closure_json_bytes(closure))
    summary = closure["summary"]
    print(
        f"built raw closure: {summary['total_count']}/"
        f"{summary['total_count']} decisions, "
        f"game={summary['game_message_count']} "
        f"expansion={summary['expansion_message_count']} "
        f"excluded={summary['non_user_facing_exclusion_count'] + summary['diagnostic_exclusion_count']} "
        f"fallback={summary['english_fallback_count']} "
        f"unresolved={summary['unresolved_count']}"
    )
    return 0


def _cmd_check_raw_closure(args: argparse.Namespace) -> int:
    closure = _build_raw_closure(args)
    expected = closure_json_bytes(closure)
    if not args.closure.is_file() or args.closure.read_bytes() != expected:
        raise MappingError(
            f"{args.closure}: raw closure differs from deterministic rebuild"
        )
    summary = closure["summary"]
    print(
        f"raw closure matches committed bytes: decisions={summary['total_count']} "
        f"game={summary['game_message_count']} "
        f"expansion={summary['expansion_message_count']} "
        f"excluded={summary['non_user_facing_exclusion_count'] + summary['diagnostic_exclusion_count']} "
        f"fallback={summary['english_fallback_count']} "
        f"unresolved={summary['unresolved_count']}"
    )
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

    for command, help_text, handler in (
        (
            "regenerate",
            "regenerate artifacts from the committed raw input snapshots",
            _cmd_regenerate,
        ),
        (
            "check",
            "compare regenerated artifacts with committed bytes",
            _cmd_check,
        ),
    ):
        source_parser = subparsers.add_parser(command, help=help_text)
        source_parser.add_argument(
            "--source-dir",
            type=Path,
            default=Path("texts/locales/source"),
        )
        source_parser.add_argument(
            "--out-dir",
            type=Path,
            default=Path("texts/locales"),
        )
        source_parser.set_defaults(handler=handler)

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

    harvest_parser = subparsers.add_parser(
        "harvest-crosswalk",
        help="harvest structural FE8U/FE8J evidence from authorized reference trees",
    )
    harvest_parser.add_argument("--fe8u-root", type=Path, required=True)
    harvest_parser.add_argument("--fe8j-root", type=Path, required=True)
    harvest_parser.add_argument(
        "--raw-source",
        type=Path,
        default=Path("texts/locales/zh-Hans/raw.json"),
    )
    harvest_parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("texts/locales/mapping/fe8u_structural_evidence.json"),
    )
    harvest_parser.add_argument(
        "--target-header",
        type=Path,
        default=Path("include/constants/msg.h"),
    )
    harvest_parser.set_defaults(handler=_cmd_harvest_crosswalk)

    for command, help_text, handler in (
        (
            "build-crosswalk",
            "build the authoritative map and coverage report from committed evidence",
            _cmd_build_crosswalk,
        ),
        (
            "check-crosswalk",
            "compare committed crosswalk artifacts with a deterministic rebuild",
            _cmd_check_crosswalk,
        ),
    ):
        crosswalk_parser = subparsers.add_parser(command, help=help_text)
        crosswalk_parser.add_argument(
            "--evidence",
            type=Path,
            default=Path("texts/locales/mapping/fe8u_structural_evidence.json"),
        )
        crosswalk_parser.add_argument(
            "--candidates",
            type=Path,
            default=Path("texts/locales/mapping/fe8j_to_fe8u.candidates.json"),
        )
        crosswalk_parser.add_argument(
            "--mapping",
            type=Path,
            default=Path("texts/locales/mapping/fe8u_target_map.json"),
        )
        crosswalk_parser.add_argument(
            "--report",
            type=Path,
            default=Path("texts/locales/mapping/fe8u_target_map.coverage.json"),
        )
        crosswalk_parser.add_argument(
            "--target-header",
            type=Path,
            default=Path("include/constants/msg.h"),
        )
        crosswalk_parser.set_defaults(handler=handler)

    for command, help_text, handler in (
        (
            "build-raw-closure",
            "build the 143-record raw-surface closure manifest",
            _cmd_build_raw_closure,
        ),
        (
            "check-raw-closure",
            "compare the raw-surface closure manifest with a deterministic rebuild",
            _cmd_check_raw_closure,
        ),
    ):
        closure_parser = subparsers.add_parser(command, help=help_text)
        closure_parser.add_argument(
            "--raw-source",
            type=Path,
            default=Path("texts/locales/zh-Hans/raw.json"),
        )
        closure_parser.add_argument(
            "--mapping",
            type=Path,
            default=Path("texts/locales/mapping/fe8u_target_map.json"),
        )
        closure_parser.add_argument(
            "--decisions",
            type=Path,
            default=Path("texts/locales/mapping/raw_surface_decisions.json"),
        )
        closure_parser.add_argument(
            "--closure",
            type=Path,
            default=Path("texts/locales/mapping/raw_surface_closure.json"),
        )
        closure_parser.add_argument(
            "--registry",
            type=Path,
            default=Path("texts/expansion/registry.json"),
        )
        closure_parser.add_argument(
            "--catalog-en",
            type=Path,
            default=Path("texts/expansion/catalog.en.json"),
        )
        closure_parser.add_argument(
            "--catalog-ja",
            type=Path,
            default=Path("texts/expansion/catalog.ja.json"),
        )
        closure_parser.add_argument(
            "--catalog-zh-hans",
            type=Path,
            default=Path("texts/expansion/catalog.zh-Hans.json"),
        )
        closure_parser.add_argument(
            "--repo-root",
            type=Path,
            default=Path("."),
        )
        closure_parser.set_defaults(handler=handler)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (LocaleSourceError, MappingError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
