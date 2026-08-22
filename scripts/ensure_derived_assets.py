#!/usr/bin/env python3
"""Pre-flight check: make sure every graphics/sound asset referenced via
`.incbin`/`INCBIN_*` actually exists on disk, regenerating any that are
missing from their checked-in sources (PNG/.pal/.aif/...) via their own
`make` pattern rules, before the main parallel build starts.

Why this exists: after `make clean`/`make clean_fast` wipes every derived
asset (.4bpp/.8bpp/.gbapal/.lz/.fk/...), a subsequent `make -j<N>` has
been observed to fail with assembler "file not found" errors for some of
those exact files, even though `make -n --debug=v` shows the dependency
graph correctly lists them as prerequisites (each one individually
rebuilds fine in isolation, even under -j). The discrepancy only shows up
in the full, large parallel graph, not in `-n` dry-run or single-target
runs -- consistent with a scheduling edge case in how GNU Make's
`.SECONDEXPANSION` + per-file `$(shell tools/scaninc ...)`-derived
prerequisites (see the `data_dep` machinery in Makefile) interacts with
`-j`, though the exact mechanism wasn't pinned down further. Rather than
rely on that machinery under load, this script independently guarantees
every referenced file exists first, so the main build's own dependency
tracking (correct for anything that already exists) never has to race
against asset regeneration for a file it forgot about.

Usage: scripts/ensure_derived_assets.py [-j N]
Exit code is 0 even if nothing needed regenerating (that's the common
case and should stay silent/fast); nonzero only if regeneration itself
fails.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

INCBIN_S_RE = re.compile(r'\.incbin\s*"([^"]+)"')
INCBIN_C_RE = re.compile(r'INCBIN_[A-Z0-9]+\("([^"]+)"')

# Not real build inputs -- test fixtures for the generated-data platform's
# own test suite, never referenced by anything make actually builds.
SKIP_SUBSTRING = "generated_data/tests/fixtures"


def find_referenced_paths():
    paths = set()
    for pattern, glob in ((INCBIN_S_RE, "*.s"), (INCBIN_C_RE, "*.c")):
        for path in REPO_ROOT.rglob(glob):
            path_str = str(path)
            if "/.git/" in path_str or "/build/" in path_str:
                continue
            # Skip by the referencing source file's own location, not the
            # referenced path -- a fixture .c can reference a path that
            # looks like an ordinary repo-relative graphics path (e.g.
            # "graphics/items/fixture_a.4bpp") with no fixture-y substring
            # of its own.
            if SKIP_SUBSTRING in path_str:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in pattern.finditer(text):
                paths.add(m.group(1))
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-j", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    referenced = find_referenced_paths()
    missing = sorted(p for p in referenced if not os.path.exists(p))

    if not missing:
        return 0

    print(f"ensure_derived_assets: regenerating {len(missing)} missing derived asset(s)...",
          file=sys.stderr)

    # Serial `make` per batch (not -j) deliberately: this is the exact
    # scenario the whole script exists to avoid racing.
    batch_size = 50
    for i in range(0, len(missing), batch_size):
        batch = missing[i:i + batch_size]
        result = subprocess.run(["make", "-k", *batch])
        if result.returncode not in (0, 2):
            # 'make -k' keeps going past individual failures and still
            # exits nonzero if anything failed; a genuinely missing
            # source (no PNG/.pal/.aif counterpart) is a real error the
            # caller needs to see, not something to paper over.
            return result.returncode

    still_missing = [p for p in missing if not os.path.exists(p)]
    if still_missing:
        print("ensure_derived_assets: still missing after regeneration attempt:",
              file=sys.stderr)
        for p in still_missing:
            print(f"  {p}", file=sys.stderr)
        return 1

    print(f"ensure_derived_assets: regenerated {len(missing)} asset(s) successfully",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
