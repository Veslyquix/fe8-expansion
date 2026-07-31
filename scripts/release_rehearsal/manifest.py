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

from scripts.release_rehearsal import allowlist as al  # noqa: E402
from scripts.release_rehearsal import archive_rehearsal as ar  # noqa: E402
from scripts.release_rehearsal import changelog as cl  # noqa: E402
from scripts.release_rehearsal import consistency as cc  # noqa: E402
from scripts.release_rehearsal import doc_links as dl  # noqa: E402
from scripts.release_rehearsal import git_source as gs  # noqa: E402
from scripts.release_rehearsal import provenance as prov  # noqa: E402
from scripts.release_rehearsal import source_guard as sg  # noqa: E402
from scripts.release_rehearsal import tree_coverage as tc  # noqa: E402
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
    "docs/release_data/export_exclusions.json",
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


SHORT_SHA_RE = re.compile(r"^[0-9a-f]{8}$")


def verify_short_sha(target_sha: str, embedded_short: str) -> None:
    """Mandatory embedded short-SHA verification for a release candidate:
    a missing/malformed/wrong-length/wrong-case value is rejected with an
    actionable, distinct message (never merely "did not match"), and the
    fixed sentinel "unknown" (scripts/modernize/expansion_config.py's own
    no-git fallback) is exactly as unacceptable as any other malformed
    value here -- a release candidate manifest must never accept an
    unresolved build identity."""
    if not isinstance(embedded_short, str) or not SHORT_SHA_RE.fullmatch(embedded_short):
        raise ManifestError(
            f"embedded short-form build commit {embedded_short!r} must be exactly "
            f"{SHORT_SHA_LEN} lowercase hex characters (e.g. not 'unknown', not missing, "
            "not wrong length/case)"
        )
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


def check_provenance(repo_root: Path, target_sha: str) -> Dict:
    """Folds four independent provenance defect classes into one report:
    (1) each entry's own resolved-fact status (`prov.evaluate`); (2) exact,
    one-record-per-member coverage against the combined included allowlist
    + excluded export-exclusions path set -- no directory-prefix/
    category-inheritance credit any more (`prov.evaluate_coverage`); (3)
    for any "submodule"-category entry, a cross-check that its declared
    `pinned_commit` actually matches the real gitlink object id Git's own
    tree records at `target_sha` (`prov.check_gitlink_pins`); and (4) for
    every "code"/"asset"-category entry, a cross-check that its declared
    `oid`/`sha256` actually match the real, live blob Git's own tree
    records at `target_sha` (`prov.check_blob_identity` -- issue #9
    mandatory correction #3: a changed/new blob whose provenance record
    was not regenerated is a "stale provenance" failure, never silently
    passed through on path-match alone). Both cross-checks are skipped
    only when `repo_root` is not a git repository at all (nothing to
    cross-check against)."""
    try:
        entries = prov.load_all(repo_root / "docs" / "release_data" / "provenance")
    except prov.ProvenanceError as error:
        raise ManifestError(str(error)) from error
    status, reasons = prov.evaluate(entries)
    allowlist_path = repo_root / "docs" / "release_data" / "source_allowlist.json"
    exclusions_path = repo_root / "docs" / "release_data" / "export_exclusions.json"
    if allowlist_path.is_file():
        allowlist = json.loads(allowlist_path.read_text(encoding="utf-8")).get("paths", [])
        # issue #9 mandatory correction #2: the required-coverage set is
        # now the *combined* included (allowlist) + excluded
        # (export-exclusions) path set -- the `mgfembp` gitlink's own
        # provenance/exclusion record must never be misreported as a
        # "ghost" entry (its path is not in the allowlist any more) nor
        # leave the allowlist itself short a "gap" for it (it was never
        # supposed to be there in the first place). See
        # scripts/release_rehearsal/tree_coverage.py.
        required_paths = list(allowlist)
        if exclusions_path.is_file():
            try:
                required_paths = tc.combined_required_paths(
                    allowlist, tc.load_exclusion_paths(exclusions_path)
                )
            except tc.TreeCoverageError as error:
                raise ManifestError(str(error)) from error
        coverage_reasons = prov.evaluate_coverage(entries, required_paths)
        if coverage_reasons:
            status = "blocked"
            reasons = sorted(set(reasons) | set(coverage_reasons))
    pin_reasons = prov.check_gitlink_pins(entries, repo_root, target_sha)
    if pin_reasons:
        status = "blocked"
        reasons = sorted(set(reasons) | set(pin_reasons))
    identity_reasons = prov.check_blob_identity(entries, repo_root, target_sha)
    if identity_reasons:
        status = "blocked"
        reasons = sorted(set(reasons) | set(identity_reasons))
    return {"status": status, "reasons": reasons}


def check_tree_coverage(repo_root: Path, target_sha: str) -> Dict:
    """Exact immutable HEAD tree coverage (issue #9 mandatory correction
    #2): the checked-in included allowlist
    (`docs/release_data/source_allowlist.json`) and the checked-in
    explicit export exclusions (`docs/release_data/export_exclusions.json`)
    must together account for *every* tracked path exactly once -- no
    gap, no overlap, no stale/mismatched exclusion record. Dispatches on
    whether `repo_root` is an actual git repository, exactly like
    `check_allowlist_exact`/`check_source_guard` above: a genuine
    non-git extracted candidate tree is closed-world-validated against
    on-disk membership instead (`tree_coverage.check_non_git_tree`),
    never causing a git invocation."""
    allowlist_path = repo_root / "docs" / "release_data" / "source_allowlist.json"
    exclusions_path = repo_root / "docs" / "release_data" / "export_exclusions.json"
    try:
        allowlist_paths = al.load_allowlist_paths(allowlist_path)
    except al.AllowlistError as error:
        raise ManifestError(str(error)) from error
    try:
        exclusion_entries = tc.load_exclusions(exclusions_path)
    except tc.TreeCoverageError as error:
        raise ManifestError(str(error)) from error

    if not gs.is_git_repo(repo_root):
        result = tc.check_non_git_tree(repo_root, allowlist_paths, exclusion_entries)
        errors = result.reasons()
        return {"ok": not errors, "errors": errors}

    result = tc.check_partition(repo_root, allowlist_paths, exclusion_entries, target_sha)
    errors = result.reasons()
    return {"ok": not errors, "errors": errors}


def check_source_guard(repo_root: Path) -> Dict:
    """Evaluates the actual source-release candidate set for `repo_root`,
    consistent with scripts/release_rehearsal/archive_rehearsal.py: a git
    working tree is scanned as its tracked-files-intersected-with-the-
    allowlist candidate set (so gitignored/untracked build byproducts --
    .dep/ output, a built ROM/ELF, host tool binaries, etc. -- sitting in
    a live development worktree can never change this report purely
    because of host/build state), while a genuine extracted archive or
    other non-git candidate tree is still scanned closed-world and fails
    closed (see sg.scan_source_release_candidate)."""
    map_hex_exceptions_path = repo_root / "docs" / "release_data" / "map_hex_exceptions.json"
    try:
        allowlist = sg.load_allowlist(repo_root / "docs" / "release_data" / "source_allowlist.json")
        map_hex_exceptions = (
            sg.load_map_hex_exceptions(map_hex_exceptions_path)
            if map_hex_exceptions_path.is_file() else frozenset()
        )
        violations = sg.scan_source_release_candidate(repo_root, allowlist, map_hex_exceptions)
    except sg.SourceGuardError as error:
        raise ManifestError(str(error)) from error
    return {
        "status": "blocked" if violations else "pass",
        "violations": [f"{path}: {rule}" for path, rule in violations],
    }


def check_allowlist_exact(repo_root: Path, target_sha: str) -> Dict:
    """Exact per-member allowlist completeness (issue #9 verifier
    remediation): every git-tracked file/gitlink at `target_sha` must have
    its own exact entry in docs/release_data/source_allowlist.json, and
    every entry must still correspond to something actually tracked --
    see scripts/release_rehearsal/allowlist.py. A brand-new tracked file
    with no allowlist entry is exactly the "unlisted tracked file" issue
    #9 requires to fail, not silently be omitted from the archive.

    `al.check()` itself dispatches on whether `repo_root` is a real git
    repository: for a non-git candidate tree (a genuine extracted
    archive), it closed-world-validates actual on-disk membership
    instead (never invoking git plumbing against it), reporting a
    present-but-unlisted file or an allowlisted member with no on-disk
    representation at all (e.g. a missing "mgfembp" gitlink mountpoint)
    exactly as actionably as the git-tracked-bijection case. A
    well-formed 40-lowercase-hex `target_sha` that does not resolve to a
    real object in an actual git repository raises
    `git_source.GitSourceError` here (propagated, never swallowed) --
    scripts/release_rehearsal/cli.py's single top-level exception
    boundary is what converts that into `EXIT_TOOLING_ERROR`, not this
    function papering over it as a soft business reason."""
    allowlist_path = repo_root / "docs" / "release_data" / "source_allowlist.json"
    errors = al.check(repo_root, allowlist_path, target_sha)
    return {"ok": not errors, "errors": errors}


def check_migrations() -> Dict:
    errors = migrations_registry.check_registry()
    return {"ok": not errors, "errors": errors}


def check_allowlist(repo_root: Path, target_sha: str) -> Dict:
    return check_allowlist_exact(repo_root, target_sha)


def check_version_ledger_and_semver(repo_root: Path, identity, changelog_report: Dict) -> Dict:
    """Folds together the version-ledger topology/candidate-agreement
    check and the changelog-declared-impact-vs-actual-delta check (see
    scripts/release_rehearsal/consistency.py) into one report, since both
    read the same ledger file."""
    ledger_path = repo_root / "docs" / "release_data" / "version_ledger.json"
    if not ledger_path.is_file():
        return {"ok": False, "errors": [f"{ledger_path} not found"], "ledger": {}}
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return {"ok": False, "errors": [f"{ledger_path}: not valid JSON: {error}"], "ledger": {}}

    errors = cc.check_version_ledger(ledger, identity.version_string)
    errors += cc.check_changelog_semver_delta(
        ledger.get("previous_supported_version"),
        identity.version_string,
        changelog_report.get("aggregate_impact", "none"),
        identity.version_major,
    )
    return {"ok": not errors, "errors": errors, "ledger": ledger}


def check_c_fallback(repo_root: Path) -> Dict:
    try:
        config_values = ec.parse_config_mk(repo_root / "config.mk")
    except ec.ConfigError as error:
        return {"ok": False, "errors": [str(error)]}
    errors = cc.check_c_fallback_metadata(repo_root, config_values)
    return {"ok": not errors, "errors": errors}


def check_migration_reachability(save_compat_epoch: int) -> Dict:
    errors = cc.check_migration_epoch_reachability(save_compat_epoch, migrations_registry.registry())
    return {"ok": not errors, "errors": errors}


def check_doc_links(repo_root: Path) -> Dict:
    broken = dl.find_broken_links(repo_root)
    errors = [f"{doc}: broken link -> {target}" for doc, target in broken]
    return {"ok": not errors, "errors": errors}


def check_rebuild(
    repo_root: Path,
    attempt_build: bool = False,
    build_command: Optional[List[str]] = None,
    output_relpaths: Optional[List[str]] = None,
) -> Dict:
    """Folds scripts/release_rehearsal/archive_rehearsal.py's rebuild
    rehearsal into the manifest. `attempt_build` defaults to False here
    (a fast eligibility-only check suitable for every `make release-check`
    run) -- eligibility (submodule initialized/approved/identity-matched)
    is still always evaluated; only the actual, potentially-heavy double
    compile-and-compare is opt-in. Never "mechanically eligible" while
    this reports anything other than `REBUILD_STATUS_VERIFIED_SUCCESS`
    (see build_manifest below) -- a blocked/not-run/failed rebuild always
    forces the overall candidate status to "blocked"."""
    return ar.rebuild_rehearsal_blocker(
        repo_root, attempt_build=attempt_build,
        build_command=build_command, output_relpaths=output_relpaths,
    )


def build_manifest(
    repo_root: Path,
    config_preset: str,
    abi: str,
    rom_size: str,
    target_sha_override: Optional[str] = None,
    embedded_short_sha: Optional[str] = None,
    attempt_rebuild_build: bool = False,
    rebuild_build_command: Optional[List[str]] = None,
    rebuild_output_relpaths: Optional[List[str]] = None,
) -> Dict:
    repo_root = Path(repo_root)
    # Resolve the exact, immutable target SHA *first* (this is the single
    # source of truth for this candidate's identity: an explicit
    # `--target-sha` override in non-git/archive mode, or the actual
    # repository's own resolved HEAD when `repo_root` is a real git root
    # -- see resolve_target_sha). It is then threaded into
    # ec.load_identity() as the build-id override so the embedded
    # `identity.build_commit` is always bound to this exact, already-
    # validated value: never a second, independent `git rev-parse` call
    # against `repo_root` (which -- for a non-git extracted tree nested
    # inside an unrelated outer repository -- could otherwise silently
    # adopt that outer repository's HEAD via git's own upward directory
    # discovery), and never the "unknown" sentinel, which would discard
    # the exact identity the non-git/archive path specifically requires
    # (issue #9 remediation).
    target_sha = resolve_target_sha(repo_root, target_sha_override)
    identity = ec.load_identity(
        config_mk_path=repo_root / "config.mk",
        config_preset=config_preset,
        abi=abi,
        rom_size=rom_size,
        repo_root=repo_root,
        build_id_override=target_sha,
    )
    if embedded_short_sha is not None:
        verify_short_sha(target_sha, embedded_short_sha)

    candidate_tag = build_candidate_tag(identity.version_string)
    missing_docs = check_required_docs(repo_root)
    changelog_report = check_changelog(repo_root)
    provenance_report = check_provenance(repo_root, target_sha)
    source_guard_report = check_source_guard(repo_root)
    migrations_report = check_migrations()
    allowlist_report = check_allowlist(repo_root, target_sha)
    tree_coverage_report = check_tree_coverage(repo_root, target_sha)
    ledger_report = check_version_ledger_and_semver(repo_root, identity, changelog_report)
    c_fallback_report = check_c_fallback(repo_root)
    migration_reachability_report = check_migration_reachability(identity.save_compat_epoch)
    doc_links_report = check_doc_links(repo_root)
    rebuild_report = check_rebuild(
        repo_root, attempt_build=attempt_rebuild_build,
        build_command=rebuild_build_command, output_relpaths=rebuild_output_relpaths,
    )

    ledger = ledger_report["ledger"]

    reasons: List[str] = []
    if missing_docs:
        reasons.append(f"missing required doc(s): {', '.join(missing_docs)}")
    if not changelog_report["ok"]:
        reasons.extend(changelog_report["errors"])
    if provenance_report["status"] != "mechanically eligible":
        reasons.extend(provenance_report["reasons"])
    if source_guard_report["status"] != "pass":
        reasons.extend(source_guard_report["violations"])
    if not migrations_report["ok"]:
        reasons.extend(migrations_report["errors"])
    if not allowlist_report["ok"]:
        reasons.extend(allowlist_report["errors"])
    if not tree_coverage_report["ok"]:
        reasons.extend(tree_coverage_report["errors"])
    if not ledger_report["ok"]:
        reasons.extend(ledger_report["errors"])
    if not c_fallback_report["ok"]:
        reasons.extend(c_fallback_report["errors"])
    if not migration_reachability_report["ok"]:
        reasons.extend(migration_reachability_report["errors"])
    if not doc_links_report["ok"]:
        reasons.extend(doc_links_report["errors"])
    if rebuild_report["status"] != ar.REBUILD_STATUS_VERIFIED_SUCCESS:
        reasons.extend(
            rebuild_report.get("reasons")
            or [f"rebuild rehearsal status is {rebuild_report['status']!r}, not {ar.REBUILD_STATUS_VERIFIED_SUCCESS!r}"]
        )

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
        "allowlist": allowlist_report,
        "tree_coverage": tree_coverage_report,
        "version_ledger": ledger_report,
        "c_fallback_metadata": c_fallback_report,
        "migration_reachability": migration_reachability_report,
        "doc_links": doc_links_report,
        "rebuild": rebuild_report,
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
