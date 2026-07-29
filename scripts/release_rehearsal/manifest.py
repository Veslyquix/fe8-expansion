#!/usr/bin/env python3
"""Release manifest and identity checks (issue #9).

Ties together config.mk's SemVer, the embedded C metadata contract
(include/expansion_metadata.h / include/save_format.h), a hypothetical
candidate tag string, the changelog, required docs, save-format
compatibility, migration declarations, provenance, and the source-release
guard into one machine report. Never creates a tag/ref -- ``candidate_tag``
is validated as text only. See docs/release_process.md.

Deliberately dependency-free (Python stdlib only); reuses
scripts/modernize/expansion_config.py rather than re-deriving version/
fingerprint logic.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "modernize"))

import expansion_config as ec  # noqa: E402

from scripts.release_rehearsal import changelog as cl  # noqa: E402
from scripts.release_rehearsal import provenance as prov  # noqa: E402
from scripts.release_rehearsal import source_guard as sg  # noqa: E402
from scripts.modernize.migrations import registry as migrations_registry  # noqa: E402

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CANDIDATE_TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHORT_SHA_LEN = 8

REQUIRED_DOCS = (
    "docs/release_process.md",
    "docs/public_api_policy.md",
    "docs/migration_registry.md",
    "docs/save_format.md",
    "docs/release_data/version_ledger.json",
    "docs/release_data/source_allowlist.json",
)


class ManifestError(ValueError):
    """An actionable, well-formed input/consistency error -- distinct from
    the expected 'blocked' business status."""


def _is_git_repo(repo_root: Path) -> bool:
    return (repo_root / ".git").exists()


def resolve_target_sha(repo_root: Path, override: Optional[str]) -> str:
    if override is not None:
        if not FULL_SHA_RE.fullmatch(override):
            raise ManifestError(
                f"--target-sha {override!r} must be an exact 40-lowercase-hex commit SHA"
            )
        return override
    if not _is_git_repo(repo_root):
        raise ManifestError(
            "no .git metadata found (an archive or non-git tree); an explicit "
            "--target-sha (exact 40-lowercase-hex) override is required"
        )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True
    )
    sha = result.stdout.strip()
    if result.returncode != 0 or not FULL_SHA_RE.fullmatch(sha):
        raise ManifestError(
            "git rev-parse HEAD did not return a clean 40-lowercase-hex SHA; "
            "pass an explicit --target-sha override"
        )
    return sha


def derive_short_sha(target_sha: str) -> str:
    """Mirrors scripts/modernize/save_format_tool.py's
    build_commit[:8] short-form derivation used for the on-media
    ExpansionSaveMeta.buildCommitShort diagnostic field."""
    return target_sha[:SHORT_SHA_LEN]


def verify_short_sha(target_sha: str, embedded_short: str) -> None:
    expected = derive_short_sha(target_sha)
    if embedded_short != expected:
        raise ManifestError(
            f"embedded short-form build commit {embedded_short!r} does not match "
            f"the first {SHORT_SHA_LEN} hex characters of the full target SHA "
            f"{target_sha!r} ({expected!r})"
        )


def build_candidate_tag(version_string: str) -> str:
    tag = f"v{version_string}"
    if not CANDIDATE_TAG_RE.fullmatch(tag):
        raise ManifestError(f"candidate tag text {tag!r} is not a valid vMAJOR.MINOR.PATCH tag")
    return tag


def check_required_docs(repo_root: Path) -> List[str]:
    return sorted(str(doc) for doc in REQUIRED_DOCS if not (repo_root / doc).is_file())


def check_changelog(repo_root: Path) -> Dict:
    ok, errors, rendered, impact = cl.check(
        repo_root / "changelog_fragments", repo_root / "CHANGELOG.md"
    )
    return {"ok": ok, "errors": errors, "aggregate_impact": impact}


def check_provenance(repo_root: Path) -> Dict:
    try:
        entries = prov.load_all(repo_root / "docs" / "release_data" / "provenance")
    except prov.ProvenanceError as error:
        raise ManifestError(str(error)) from error
    status, reasons = prov.evaluate(entries)
    allowlist_path = repo_root / "docs" / "release_data" / "source_allowlist.json"
    if allowlist_path.is_file():
        allowlist = json.loads(allowlist_path.read_text(encoding="utf-8")).get("paths", [])
        gaps = prov.coverage_gaps(entries, allowlist)
        if gaps:
            status = "blocked"
            reasons = sorted(set(reasons) | {f"missing provenance entry for {path}" for path in gaps})
    return {"status": status, "reasons": reasons}


def check_source_guard(repo_root: Path) -> Dict:
    try:
        allowlist = sg.load_allowlist(repo_root / "docs" / "release_data" / "source_allowlist.json")
        violations = sg.scan_tree(repo_root, allowlist)
    except sg.SourceGuardError as error:
        raise ManifestError(str(error)) from error
    return {
        "status": "blocked" if violations else "pass",
        "violations": [f"{path}: {rule}" for path, rule in violations],
    }


def check_migrations() -> Dict:
    errors = migrations_registry.check_registry()
    return {"ok": not errors, "errors": errors}


def build_manifest(
    repo_root: Path,
    config_preset: str,
    abi: str,
    rom_size: str,
    target_sha_override: Optional[str] = None,
    embedded_short_sha: Optional[str] = None,
) -> Dict:
    repo_root = Path(repo_root)
    identity = ec.load_identity(
        config_mk_path=repo_root / "config.mk",
        config_preset=config_preset,
        abi=abi,
        rom_size=rom_size,
        repo_root=repo_root,
    )
    target_sha = resolve_target_sha(repo_root, target_sha_override)
    if embedded_short_sha is not None:
        verify_short_sha(target_sha, embedded_short_sha)

    candidate_tag = build_candidate_tag(identity.version_string)
    missing_docs = check_required_docs(repo_root)
    changelog_report = check_changelog(repo_root)
    provenance_report = check_provenance(repo_root)
    source_guard_report = check_source_guard(repo_root)
    migrations_report = check_migrations()

    ledger_path = repo_root / "docs" / "release_data" / "version_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {}

    reasons: List[str] = []
    if missing_docs:
        reasons.append(f"missing required doc(s): {', '.join(missing_docs)}")
    if not changelog_report["ok"]:
        reasons.extend(changelog_report["errors"])
    if provenance_report["status"] != "approved":
        reasons.extend(provenance_report["reasons"])
    if source_guard_report["status"] != "pass":
        reasons.extend(source_guard_report["violations"])
    if not migrations_report["ok"]:
        reasons.extend(migrations_report["errors"])

    status = "blocked" if reasons else "mechanically eligible"

    return {
        "version_string": identity.version_string,
        "version_packed": identity.version_packed,
        "candidate_tag": candidate_tag,
        "target_sha": target_sha,
        "target_sha_short": derive_short_sha(target_sha),
        "config_fingerprint": identity.config_fingerprint,
        "save_compat_epoch": identity.save_compat_epoch,
        "previous_supported_version": ledger.get("previous_supported_version"),
        "next_supported_version": ledger.get("next_supported_version"),
        "docs": {"missing": missing_docs},
        "changelog": changelog_report,
        "provenance": provenance_report,
        "source_guard": source_guard_report,
        "migrations": migrations_report,
        "status": status,
        "reasons": reasons,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--config", default="release", choices=("debug", "release"))
    parser.add_argument("--abi", default="aapcs", choices=("aapcs", "apcs-gnu"))
    parser.add_argument("--rom-size", default="16M")
    parser.add_argument("--target-sha", default=None)
    parser.add_argument("--embedded-short-sha", default=None)
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(
            args.repo_root,
            args.config,
            args.abi,
            args.rom_size,
            target_sha_override=args.target_sha,
            embedded_short_sha=args.embedded_short_sha,
        )
    except (ManifestError, ec.ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"status: {manifest['status']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
