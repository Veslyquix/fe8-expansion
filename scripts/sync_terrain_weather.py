#!/usr/bin/env python3
"""Copy each class's Normal-weather movement-cost table onto its Rain/Snow
counterparts in src/data_terrains.c.

This repo currently ships Rain/Snow variants that are frequently stale
relative to their Normal table (weather no longer meaningfully changes
movement cost for most classes in this expansion). Rather than hand-editing
three near-identical 68-entry designated-initializer arrays every time a
Normal table changes, run this after editing any `TerrainTable_MovCost_*Normal`
array and it will overwrite the matching `*Rain`/`*Snow` arrays' bodies to
match, leaving everything else in the file untouched.

Only touches classes that already have both a `*Rain` and `*Snow` array
(e.g. Soldier has none of either by default in vanilla and needs both added
by hand once -- see the `TerrainTable_MovCost_SoldierT1Rain`/`...Snow` arrays
and their header comments in src/data_terrains.c). New classes still need a
Rain/Snow array stub added manually before this script will start syncing
them; it never creates new arrays, only re-fills existing ones.

Usage:
    python3 scripts/sync_terrain_weather.py [--check] [path/to/data_terrains.c]

--check: exit 1 if any Rain/Snow array would change, without modifying the
file (useful in CI). Default path is src/data_terrains.c relative to the
repo root.
"""
import re
import sys
from pathlib import Path

ARRAY_RE = re.compile(
    r"CONST_DATA s8 (TerrainTable_MovCost_\w+)\[\] = \{\n(.*?)\n\};",
    re.DOTALL,
)


def find_arrays(text):
    """Return {name: (start, end, body)} for every movecost array in text."""
    arrays = {}
    for m in ARRAY_RE.finditer(text):
        arrays[m.group(1)] = (m.start(), m.end(), m.group(2))
    return arrays


def sync(text):
    arrays = find_arrays(text)
    replacements = []  # (start, end, new_body_text)
    changed = []

    for name, (_, _, body) in arrays.items():
        if not name.endswith("Normal"):
            continue
        base = name[: -len("Normal")]
        for suffix in ("Rain", "Snow"):
            target_name = base + suffix
            target = arrays.get(target_name)
            if target is None:
                continue
            t_start, t_end, t_body = target
            if t_body == body:
                continue
            replacements.append((t_start, t_end, f"CONST_DATA s8 {target_name}[] = {{\n{body}\n}};"))
            changed.append(target_name)

    # Apply from the end of the file backwards so earlier offsets stay valid.
    replacements.sort(key=lambda r: r[0], reverse=True)
    new_text = text
    for start, end, new_block in replacements:
        new_text = new_text[:start] + new_block + new_text[end:]

    return new_text, sorted(changed)


def main(argv):
    check_only = "--check" in argv
    argv = [a for a in argv if a != "--check"]

    repo_root = Path(__file__).resolve().parent.parent
    path = Path(argv[0]) if argv else repo_root / "src" / "data_terrains.c"

    text = path.read_text()
    new_text, changed = sync(text)

    if not changed:
        print("no Rain/Snow tables out of sync with their Normal table")
        return 0

    if check_only:
        print(f"{len(changed)} table(s) out of sync: {', '.join(changed)}")
        return 1

    path.write_text(new_text)
    print(f"synced {len(changed)} table(s): {', '.join(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
