#!/usr/bin/env python3
"""Sync generated-data JSON edits into the matching hand C reference files.

This is intentionally conservative. Some generated-data tables emit standalone
C fragments that are not 1:1 replacements for their hand sources (for example
terrain stats/move costs both compare against pieces of src/data_terrains.c).
By default we only sync tables where the generated output filename matches the
hand C filename exactly.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_TABLES = ("characters", "classes", "items", "supports")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_generate(root: Path, table: str, out_dir: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "scripts.generated_data",
        "generate",
        "--table",
        table,
        "--out-dir",
        str(out_dir),
        "--inventory",
        str(out_dir / f"{table}_inventory.md"),
        "--no-roundtrip",
    ]

    env = os.environ.copy()
    env.setdefault("FE8_ITEM_ID_CAP", "")

    subprocess.run(cmd, cwd=root, env=env, check=True)


def resolve_table_paths(root: Path, table: str) -> tuple[Path, Path]:
    # Import after resolving cwd so the generated-data registry sees repo paths.
    sys.path.insert(0, str(root))

    from scripts.generated_data import registry  # noqa: F401
    from scripts.generated_data.schema import REGISTRY

    schema = REGISTRY.resolve(table)

    if not schema.default_hand_source:
        raise ValueError(f"{table}: no hand C source is registered")

    if not schema.default_output_name:
        raise ValueError(f"{table}: no generated C output is registered")

    hand_source = root / schema.default_hand_source

    if hand_source.name != schema.default_output_name:
        raise ValueError(
            f"{table}: generated output {schema.default_output_name!r} is not a "
            f"direct replacement for {schema.default_hand_source!r}"
        )

    return hand_source, Path(schema.default_output_name)


def sync_table(root: Path, table: str, dry_run: bool) -> bool:
    hand_source, output_name = resolve_table_paths(root, table)

    with tempfile.TemporaryDirectory(prefix="sync-generated-data-") as tmp:
        out_dir = Path(tmp)
        run_generate(root, table, out_dir)

        generated = out_dir / output_name
        if not generated.exists():
            raise FileNotFoundError(f"{table}: expected generated file {generated}")

        new_bytes = generated.read_bytes()
        old_bytes = hand_source.read_bytes() if hand_source.exists() else None

        if old_bytes == new_bytes:
            print(f"up to date: {hand_source}")
            return False

        if dry_run:
            print(f"would update: {hand_source}")
            return True

        shutil.copyfile(generated, hand_source)
        print(f"updated: {hand_source}")
        return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy generated-data JSON edits into matching src/data_*.c reference files."
    )
    parser.add_argument(
        "tables",
        nargs="*",
        default=DEFAULT_TABLES,
        help=f"tables to sync (default: {", ".join(DEFAULT_TABLES)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and report what would change without writing files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()

    changed = 0
    for table in args.tables:
        try:
            changed += int(sync_table(root, table, args.dry_run))
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    action = "would update" if args.dry_run else "updated"
    print(f"done: {action} {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
