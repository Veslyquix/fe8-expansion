#!/usr/bin/env python3
"""Stale save-compatibility-epoch claim regression guard (issue #9
verifier remediation).

Independent verification found that this branch could carry a stale
*current-state* claim about ``EXPANSION_SAVE_COMPAT_EPOCH`` -- e.g. a
feature header asserting "(EXPANSION_SAVE_COMPAT_EPOCH stays 1)" after a
later, unrelated commit (issue #18 sprint 2) bumped the *actual* current
epoch from 1 to 2. Such a comment is not merely cosmetic: it is a
publication-integrity fact a reviewer might reasonably trust without
re-deriving it from config.mk themselves.

This module scans a fixed set of release-relevant docs/headers for any
sentence that asserts a *specific, literal* epoch value as the *current*
one (using words like "stays"/"remains"/"unchanged at"/"is still"/"holds
at") and flags it when that literal value does not match the actual,
live ``EXPANSION_SAVE_COMPAT_EPOCH`` (read once, authoritatively, via
``scripts/modernize/expansion_config.py``'s own config.mk parser -- never
re-implemented here).

Deliberately narrow and conservative: a *historical migration* statement
(e.g. "Bump EXPANSION_SAVE_COMPAT_EPOCH ... from 1 to 2", or a table cell
reading "`1` -> `2`") never matches this module's CURRENT_CLAIM_RE at
all -- that pattern only requires one of a small fixed set of
"still-true-today" verbs immediately after the epoch keyword, which a
transition sentence never uses. This is intentionally an allowlist of
*shapes*, not a denylist of numbers: a correct, present-tense claim that
happens to match the live epoch is never flagged.

Deliberately dependency-free (Python stdlib only), matching this
repository's other release-rehearsal tooling.

Exit codes (CLI): 0 clean, 1 stale claim(s) found, 2 invocation/I/O error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "modernize"))

import expansion_config as ec  # noqa: E402

# The release-process-relevant surface this scan owns: headers that are
# free to describe a feature's own save-format impact, plus the release
# docs/evidence that summarize compatibility facts for a reviewer. Scoped
# deliberately (not every *.h/*.md in the repository) to stay within
# issue #9's own file domain.
DEFAULT_TARGETS: Tuple[str, ...] = (
    "include/expansion_starter_content.h",
    "include/expansion_config.h",
    "include/save_format.h",
    "include/expansion_save_prefs.h",
    "docs/config_identity.md",
    "docs/release_process.md",
    "docs/save_format.md",
    "docs/migration_registry.md",
    "docs/release_closure_candidate.md",
    "CHANGELOG.md",
)

# Any spelling of the epoch identifier this project uses, in prose or code.
_EPOCH_KEYWORD = r"(?:FE8_)?EXPANSION_SAVE_COMPAT_EPOCH|save[- ]?compat(?:ibility)?\s+epoch|compat\s+epoch"

# A "this is still the current value" claim: the epoch keyword, followed
# (within a short window, same line) by one of a small fixed set of
# present-tense-permanence verbs, then a literal integer. Deliberately
# does NOT include generic verbs like bare "is" (too easily matched
# inside unrelated prose) or transition phrasing ("from X to Y", "X->Y",
# "X -> Y") -- those never trigger this pattern at all.
CURRENT_CLAIM_RE = re.compile(
    r"(?:" + _EPOCH_KEYWORD + r")"
    r"[^\n]{0,25}?"
    r"\b(?:stays|staying|remains|remaining|unchanged at|holds at|is still|stayed at|kept at|fixed at)\b"
    r"[^\n]{0,10}?(\d+)",
    re.IGNORECASE,
)

# Independent-review remediation: docs/config_identity.md's own
# "Settings reference" table documents EXPANSION_SAVE_COMPAT_EPOCH's
# *Default* column as plain, present-tense fact (no "stays"/"remains"
# verb at all -- it is a canonical settings table, not a claim
# sentence), so CURRENT_CLAIM_RE above structurally can never see it.
# A broad regex loosened to also catch this shape would risk flagging
# legitimate historical migration prose elsewhere (e.g.
# docs/migration_registry.md's "bumped once, from `1` to `2`"), which
# issue #9 explicitly forbids. Instead this is a narrow, *structural*
# semantic cross-check: parse this one named canonical table's own
# `EXPANSION_SAVE_COMPAT_EPOCH` row and compare its Default column,
# and only that column, against the live epoch -- scoped by exact file
# name, never applied speculatively to some other markdown table shape.
CANONICAL_TABLE_FILENAME = "config_identity.md"
CANONICAL_TABLE_SETTING = "EXPANSION_SAVE_COMPAT_EPOCH"
_CANONICAL_TABLE_ROW_RE = re.compile(
    r"^\|\s*`" + re.escape(CANONICAL_TABLE_SETTING) + r"`\s*\|(?P<constraint>[^|]*)\|(?P<default>[^|]*)\|"
)


def _find_stale_canonical_table_default(relpath: str, text: str, live_epoch: int) -> List[str]:
    """Semantically cross-checks the canonical settings-reference
    table's own EXPANSION_SAVE_COMPAT_EPOCH row's *Default* column
    against the live, authoritative epoch. Only ever inspects a file
    literally named ``config_identity.md`` (by basename, regardless of
    the relative path a caller passes in -- so a synthetic test fixture
    using that exact filename is checked the same way the real repo's
    ``docs/config_identity.md`` is); every other target file is
    untouched by this function. A row whose Default column carries no
    parseable integer at all is left alone -- this function only ever
    flags a literal, present *mismatched* number, never a formatting
    change."""
    if Path(relpath).name != CANONICAL_TABLE_FILENAME:
        return []
    findings: List[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = _CANONICAL_TABLE_ROW_RE.match(line)
        if not match:
            continue
        digits = re.search(r"\d+", match.group("default"))
        if digits is None:
            continue
        claimed = int(digits.group(0))
        if claimed != live_epoch:
            findings.append(
                f"{relpath}:{lineno}: canonical settings-reference table claims the "
                f"{CANONICAL_TABLE_SETTING} default is currently {claimed} but the live "
                f"config.mk value is {live_epoch} -- stale canonical-table default "
                f"(context: {line.strip()!r})"
            )
    return findings


class EpochClaimError(ValueError):
    """An actionable invocation/I/O error -- distinct from a stale-claim finding."""


def current_epoch(repo_root: Path) -> int:
    """The single, authoritative live epoch value -- config.mk's
    EXPANSION_SAVE_COMPAT_EPOCH, parsed the exact same way every other
    release-rehearsal/modern-build tool does (never re-derived here)."""
    repo_root = Path(repo_root)
    config = ec.parse_config_mk(repo_root / "config.mk")
    return ec.validate_save_compat_epoch(config["EXPANSION_SAVE_COMPAT_EPOCH"])


def find_stale_epoch_claims(
    repo_root: Path, target_relpaths: Tuple[str, ...] = DEFAULT_TARGETS, epoch: "int | None" = None,
) -> List[str]:
    """Returns a list of human-readable findings (empty means clean).
    Each finding names the exact file, line number, claimed value, and
    the actual current epoch. A target file that does not exist is
    silently skipped (this module only ever *scans* -- it is not itself
    the "which docs must exist" contract; see doc_links.py/manifest.py's
    own REQUIRED_DOCS for that)."""
    repo_root = Path(repo_root)
    live_epoch = epoch if epoch is not None else current_epoch(repo_root)
    findings: List[str] = []
    for relpath in target_relpaths:
        path = repo_root / relpath
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in CURRENT_CLAIM_RE.finditer(line):
                claimed = int(match.group(1))
                if claimed != live_epoch:
                    findings.append(
                        f"{relpath}:{lineno}: claims EXPANSION_SAVE_COMPAT_EPOCH is currently "
                        f"{claimed} but the live config.mk value is {live_epoch} -- stale "
                        f"current-state claim (context: {line.strip()!r})"
                    )
        findings.extend(_find_stale_canonical_table_default(relpath, text, live_epoch))
    return findings


def check(repo_root: Path, target_relpaths: Tuple[str, ...] = DEFAULT_TARGETS) -> dict:
    """Manifest-shaped report: `{"ok": bool, "errors": [...]}`."""
    findings = find_stale_epoch_claims(repo_root, target_relpaths)
    return {"ok": not findings, "errors": findings}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("targets", nargs="*", default=None, help="override the default target set")
    args = parser.parse_args(argv)

    try:
        targets = tuple(args.targets) if args.targets else DEFAULT_TARGETS
        findings = find_stale_epoch_claims(args.repo_root, targets)
    except (OSError, ec.ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    for finding in findings:
        print(finding)
    if findings:
        print(f"epoch_claims: {len(findings)} stale claim(s)", file=sys.stderr)
        return 1
    print("epoch_claims: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
