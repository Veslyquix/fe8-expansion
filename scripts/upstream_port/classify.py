"""Deterministic, path-pattern-based classification and risk tagging.

Pure function of the changed-path string(s) -- no git calls, no clock, no
network -- so results are 100% reproducible given the same commit content.
"""

from __future__ import annotations

import fnmatch
from typing import Dict, FrozenSet, List, Sequence, Tuple

from . import constants

# Ordered (category, [fnmatch patterns]) rules. First matching category wins.
# fnmatch's '*' matches across path separators, so "src/*" already matches
# any nested path under src/ -- no special "**" handling is required.
_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("linker", (
        "ldscript.txt",
        "linker_script_*.txt",
        "linker/*",
    )),
    ("build", (
        "Makefile",
        "*.mk",
        "build_tools.sh",
        "clean_tools.sh",
        "config.mk",
        "objects.lst",
    )),
    ("symbol", (
        "sym_*.txt",
        "*.map",
        "*.sym",
    )),
    ("docs", (
        "*.md",
        "docs/*",
        "README*",
        "CONTRIBUTING*",
        "CLAUDE.md",
    )),
    ("config", (
        ".github/*",
        "buddy.yml",
        "compile_flags.txt",
        ".gitignore",
        "*.yml",
        "*.yaml",
    )),
    ("tools", (
        "scripts/*",
        "tools/*",
        "asmdiff.sh",
        "mgfembp/*",
        "*.sh",
        "*.py",
    )),
    ("data", (
        "src/data/*",
        "graphics/*",
        "banim/*",
        "sound/*",
        "texts/*",
        "*.json",
    )),
    ("code", (
        "src/*",
        "include/*",
        "asm/*",
    )),
)

# Filenames/globs known, from this fork's history, to be hotspots where the
# modern (expansion) build diverges from canonical upstream -- touching these
# is flagged even when the category itself (build/linker) doesn't already
# imply risk, to make the flag's provenance explicit and greppable.
_KNOWN_DIVERGENCE_HOTSPOTS: Tuple[str, ...] = (
    "Makefile",
    "modern.mk",
    "ldscript.txt",
    "linker_script_banim.txt",
    "linker_script_sound.txt",
    "generated_data.mk",
    "config.mk",
    "songs.mk",
    "json_data_rules.mk",
    "graphics_file_rules.mk",
    "make_tools.mk",
    "scripts/artifact_guard.py",
    "scripts/shiftcheck/*",
    "scripts/generated_data/*",
)

_CATEGORY_RISK_TAG: Dict[str, str] = {
    "linker": "linker-conflict-risk",
    "build": "modern-build-divergence-risk",
    "symbol": "symbol-table-conflict-risk",
}


def classify_path(path: str) -> str:
    """Return the single best-matching category for a changed path."""
    for category, patterns in _RULES:
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return category
    return "other"


def classify_paths(paths: Sequence[str]) -> Dict[str, str]:
    return {path: classify_path(path) for path in paths}


def risk_flags_for_paths(paths: Sequence[str]) -> List[str]:
    """Deterministic, sorted set of risk tags implied by `paths`."""
    tags = set()
    for path in paths:
        category = classify_path(path)
        tag = _CATEGORY_RISK_TAG.get(category)
        if tag:
            tags.add(tag)
        for hotspot in _KNOWN_DIVERGENCE_HOTSPOTS:
            if fnmatch.fnmatch(path, hotspot):
                tags.add("known-fork-divergence-hotspot")
                break
    return sorted(tags)


def category_summary(paths: Sequence[str]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for path in paths:
        cat = classify_path(path)
        summary[cat] = summary.get(cat, 0) + 1
    return summary


assert set(cat for cat, _ in _RULES) <= set(constants.CATEGORIES)
