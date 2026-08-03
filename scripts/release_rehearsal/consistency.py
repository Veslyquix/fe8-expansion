#!/usr/bin/env python3
"""Manifest cross-consistency validators (issue #9 verifier remediation).

Everything in this module answers one question: do two (or more)
independently-maintained facts about this repository actually agree?
Each function below returns a flat list of human-readable, actionable
error strings (empty means consistent) -- never raises for an ordinary
"these disagree" finding, since that is exactly the kind of fact
``scripts/release_rehearsal/manifest.py`` folds into its own `"reasons"`/
`"status"` fields rather than crashing on.

Covers:

* the version ledger's own internal shape/topology (unique versions,
  exactly one ``"current"`` entry, previous/current/next ordering, valid
  EOL dates) *and* its agreement with the actual candidate version being
  built;
* the changelog's declared aggregate SemVer impact versus the actual
  version delta between the ledger's previous and the candidate version,
  honoring this project's documented pre-1.0 SemVer carve-out (see
  docs/public_api_policy.md);
* ``include/expansion_config.h``'s ``#ifndef``-guarded C fallback literals
  (version/ROM-identity/save-epoch, plus the config-fingerprint
  placeholder's shape) against ``config.mk``'s own resolved values -- that
  header's own comment already claims these "match config.mk's own
  defaults exactly"; nothing mechanically enforced that claim before now;
* the save-format migration registry's epoch reachability versus
  ``config.mk``'s current ``EXPANSION_SAVE_COMPAT_EPOCH``.

Deliberately dependency-free (Python stdlib only).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scripts.release_rehearsal import git_source as gs

VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_LEDGER_STATUS = ("current", "supported", "eol")

# A `previous_supported_version`/`next_supported_version` reference
# (issue #9 residual-hardening) must resolve to its own real "supported"
# ledger entry whose status is compatible with what that reference
# actually means: a previous version has already been superseded (it may
# still be actively "supported" -- e.g. an overlapping maintenance
# window -- or already "eol"), so either status is compatible, but never
# "current" (that status is exclusively the current_version's). A next
# version, by definition, has not superseded (or ended support for)
# anything yet, so only "supported" is compatible -- neither "current"
# (reserved for current_version) nor "eol" (a not-yet-current version
# cannot already be end-of-life).
_PREVIOUS_COMPATIBLE_STATUSES = ("supported", "eol")
_NEXT_COMPATIBLE_STATUSES = ("supported",)
REQUIRED_LEDGER_KEYS = (
    "current_version", "previous_supported_version", "next_supported_version", "supported",
)

BUMP_RANK = {"none": 0, "patch": 1, "minor": 2, "major": 3}
RANK_NAME = {rank: name for name, rank in BUMP_RANK.items()}

FALLBACK_HEADER_RELPATH = "include/expansion_config.h"
_FINGERPRINT_MACRO = "FE8_EXPANSION_CONFIG_FINGERPRINT"
_DEFINE_LINE_RE = re.compile(r'^\s*#define\s+(FE8_EXPANSION_[A-Z0-9_]+)\s+(.+?)\s*$')


class ConsistencyError(ValueError):
    """An input is too malformed to even classify (e.g. an unparseable
    version string) -- distinct from an ordinary list-of-reasons finding."""


def _check_reference_topology(
    supported, label: str, version: Optional[str], compatible_statuses: Tuple[str, ...]
) -> List[str]:
    """Validates one non-null `previous_supported_version`/
    `next_supported_version` reference against the actual `supported`
    array: it must exist there (exactly once -- never zero, never more
    than one), and that one entry's `status` must be one of
    `compatible_statuses`. Returns an empty list for a `None` reference
    (nothing to validate) or an already-malformed version string (the
    caller's own MAJOR.MINOR.PATCH format check already reports that
    distinctly; piling on here would be noise, not a new fact)."""
    if version is None or not VERSION_RE.fullmatch(str(version)):
        return []
    matches = [
        entry for entry in supported
        if isinstance(entry, dict) and entry.get("version") == version
    ]
    if not matches:
        return [
            f"version ledger {label} {version!r} does not appear as its own entry in the "
            "'supported' array -- every non-null previous/next supported version must be "
            "listed there"
        ]
    errors = []
    if len(matches) > 1:
        errors.append(
            f"version ledger {label} {version!r} matches {len(matches)} 'supported' entries; "
            "it must be exactly one unique ledger entry"
        )
    status = matches[0].get("status")
    if status not in compatible_statuses:
        errors.append(
            f"version ledger {label} {version!r}'s 'supported' entry has status {status!r}, "
            f"which is not a compatible status for {label} (expected one of {compatible_statuses!r})"
        )
    return errors


def parse_version(version: str) -> Tuple[int, int, int]:
    match = VERSION_RE.fullmatch(str(version))
    if not match:
        raise ConsistencyError(f"{version!r} is not a valid MAJOR.MINOR.PATCH version")
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


# --- Version ledger topology -------------------------------------------------


def check_version_ledger(ledger: Dict, candidate_version: str) -> List[str]:
    """Structural + topology + candidate-agreement validation of
    docs/release_data/version_ledger.json. See module docstring."""
    missing_keys = [key for key in REQUIRED_LEDGER_KEYS if key not in ledger]
    if missing_keys:
        return [f"version ledger missing required key(s): {', '.join(missing_keys)}"]

    errors: List[str] = []
    current = ledger["current_version"]
    previous = ledger["previous_supported_version"]
    nxt = ledger["next_supported_version"]
    supported = ledger["supported"]

    for label, value in (
        ("current_version", current),
        ("previous_supported_version", previous),
        ("next_supported_version", nxt),
    ):
        if value is not None and not VERSION_RE.fullmatch(str(value)):
            errors.append(f"version ledger {label} {value!r} is not a valid MAJOR.MINOR.PATCH version or null")

    if not isinstance(supported, list) or not supported:
        errors.append("version ledger 'supported' must be a non-empty array")
        supported = []

    seen_versions: List[str] = []
    current_status_versions: List[str] = []
    # Issue #9 residual-hardening: every syntactically-valid recorded
    # `supported[]` version tuple, gathered alongside (never replacing)
    # `seen_versions` above -- used below to detect a
    # previous_supported_version/next_supported_version reference that is
    # merely *some* older/newer recorded version rather than the true
    # *adjacent* one (see the betweenness check after the ordering checks
    # below).
    recorded_version_tuples: List[Tuple[str, Tuple[int, int, int]]] = []
    for index, entry in enumerate(supported):
        if not isinstance(entry, dict):
            errors.append(f"version ledger supported[{index}] must be an object")
            continue
        version = entry.get("version")
        status = entry.get("status")
        eol = entry.get("eol")
        if isinstance(version, str) and VERSION_RE.fullmatch(version):
            seen_versions.append(version)
            recorded_version_tuples.append((version, parse_version(version)))
        else:
            errors.append(f"version ledger supported[{index}].version {version!r} is not a valid version")
        if status not in VALID_LEDGER_STATUS:
            errors.append(f"version ledger supported[{index}].status {status!r} not in {VALID_LEDGER_STATUS}")
        elif status == "current":
            if isinstance(version, str):
                current_status_versions.append(version)
            # issue #9 residual-hardening: a fresh, independent verifier
            # reproduced a `status:"current"` entry that also carried a
            # non-null EOL date being silently accepted. The version
            # actually being rehearsed right now cannot simultaneously be
            # end-of-life -- see docs/public_api_policy.md's "Support,
            # EOL, and urgent-fix policy" ("until [a maintainer ends
            # support] it stays null").
            if eol is not None:
                errors.append(
                    f"version ledger supported[{index}] has status:'current' but a non-null "
                    f"eol {eol!r} -- a status:'current' entry must not also be marked "
                    "end-of-life (eol must be null while a version is current)"
                )
        if eol is not None and not ISO_DATE_RE.fullmatch(str(eol)):
            errors.append(f"version ledger supported[{index}].eol {eol!r} is not null or an ISO-8601 date")

    if len(seen_versions) != len(set(seen_versions)):
        dupes = sorted({version for version in seen_versions if seen_versions.count(version) > 1})
        errors.append(f"version ledger 'supported' has duplicate version entries: {dupes}")

    if len(current_status_versions) != 1:
        errors.append(
            "version ledger 'supported' must have exactly one status:'current' entry, "
            f"found {len(current_status_versions)}"
        )
    elif VERSION_RE.fullmatch(str(current)) and current_status_versions[0] != current:
        errors.append(
            f"version ledger current_version {current!r} does not match the status:'current' "
            f"supported entry {current_status_versions[0]!r}"
        )

    if VERSION_RE.fullmatch(str(current)) and str(candidate_version) != str(current):
        errors.append(
            f"candidate version {candidate_version!r} (config.mk) does not match version ledger "
            f"current_version {current!r} -- update docs/release_data/version_ledger.json"
        )

    def _tuple_or_none(value):
        return parse_version(value) if value is not None and VERSION_RE.fullmatch(str(value)) else None

    current_t = _tuple_or_none(current)
    previous_t = _tuple_or_none(previous)
    next_t = _tuple_or_none(nxt)

    if previous_t is not None and current_t is not None:
        if previous_t == current_t:
            errors.append("version ledger previous_supported_version must not equal current_version")
        elif previous_t > current_t:
            errors.append("version ledger previous_supported_version must be less than current_version")
    if next_t is not None and current_t is not None:
        if next_t == current_t:
            errors.append("version ledger next_supported_version must not equal current_version")
        elif next_t < current_t:
            errors.append("version ledger next_supported_version must be greater than current_version")
    if previous_t is not None and next_t is not None and previous_t == next_t:
        errors.append("version ledger previous_supported_version and next_supported_version must not be equal")

    # Issue #9 residual-hardening (SemVer adjacency): a fresh, independent
    # verifier reproduced `previous_supported_version` accepted as long as
    # it is *some* recorded version below current_version -- even when
    # another recorded `supported[]` entry actually lies strictly between
    # it and current_version, i.e. previous_supported_version was not the
    # true, adjacent predecessor. That silently inflates the apparent
    # SemVer delta check_changelog_semver_delta() computes (a distant,
    # skipped-over predecessor can make a small real bump look like a
    # much bigger one), and is never acceptable merely because the older
    # version remains "supported"/"eol" -- adjacency is a fact about the
    # *complete recorded set* (parsed and compared as SemVer tuples, not
    # inferred from `supported[]`'s own array order, which this schema
    # never guarantees), not a status. Symmetrically for
    # next_supported_version and any recorded version strictly between
    # current_version and it.
    if previous_t is not None and current_t is not None and previous_t < current_t:
        intervening = sorted(
            version for version, version_t in recorded_version_tuples
            if previous_t < version_t < current_t
        )
        if intervening:
            errors.append(
                f"version ledger previous_supported_version {previous!r} is not the adjacent "
                f"predecessor of current_version {current!r}: recorded 'supported' "
                f"entr{'y' if len(intervening) == 1 else 'ies'} {intervening!r} lies strictly "
                "between them -- previous_supported_version must be the closest recorded "
                "version below current_version, not merely any older one (this would "
                "otherwise inflate the apparent SemVer bump versus the true last release)"
            )
    if next_t is not None and current_t is not None and current_t < next_t:
        intervening = sorted(
            version for version, version_t in recorded_version_tuples
            if current_t < version_t < next_t
        )
        if intervening:
            errors.append(
                f"version ledger next_supported_version {nxt!r} is not the adjacent successor "
                f"of current_version {current!r}: recorded 'supported' "
                f"entr{'y' if len(intervening) == 1 else 'ies'} {intervening!r} lies strictly "
                "between them -- next_supported_version must be the closest recorded version "
                "above current_version, not merely any newer one"
            )

    # issue #9 residual-hardening: a fresh, independent verifier
    # reproduced `previous_supported_version` (and, symmetrically,
    # `next_supported_version`) accepted even when absent from the
    # `supported` array entirely. Every non-null previous/next reference
    # must resolve to its own real, unique, status-compatible ledger
    # entry -- never a dangling version string with no backing record.
    for label, referenced_version, compatible_statuses in (
        ("previous_supported_version", previous, _PREVIOUS_COMPATIBLE_STATUSES),
        ("next_supported_version", nxt, _NEXT_COMPATIBLE_STATUSES),
    ):
        errors.extend(
            _check_reference_topology(supported, label, referenced_version, compatible_statuses)
        )

    return errors


# --- Immutable annotated release-tag authority (issue #9 SemVer trust- ---
# boundary fix) -------------------------------------------------------------
#
# `check_version_ledger` above only validates the ledger's own internal
# shape/topology and its self-consistency -- it never asks whether
# `previous_supported_version` is actually *true*. These two functions
# are that separate, fail-closed authority cross-check: in a real git
# repository, the true immediate predecessor is derived exclusively from
# `git_source`'s immutable, annotated `expansion/MAJOR.MINOR.PATCH`
# release-tag history (`check_release_tag_authority`); for a genuine
# non-git/archive candidate tree, which has no local tag history to
# derive anything from at all, an explicit, external, protected
# release-history attestation file bound to the exact target commit and
# current version is required instead (`check_release_tag_authority_non_git`)
# -- a missing attestation is never silently treated as "no predecessor"
# (that would let a non-git candidate fabricate an empty release history
# for free); it is its own explicit, actionable finding.


RELEASE_HISTORY_ATTESTATION_SCHEMA_VERSION = 1


class ReleaseHistoryAttestationError(ValueError):
    """A malformed/unreadable non-git external release-history
    attestation file -- an actionable schema/IO defect, distinct from an
    ordinary "attestation disagrees with this candidate" business
    finding (which is reported as a plain string, not raised)."""


def load_release_history_attestation(path: Path) -> Dict:
    """Validated loader for a non-git candidate's external, protected
    release-history attestation file: wraps JSON decode/IO/schema/type/
    key errors into one actionable `ReleaseHistoryAttestationError` with
    the file's own path in the message (never a raw traceback/
    `JSONDecodeError`) -- the same defensive-loader discipline as
    `allowlist.load_allowlist_paths`/`load_allowlist_modes`. Returns a
    plain dict with exactly the three bound facts this attestation
    exists to carry: `target_sha`, `current_version`,
    `previous_supported_version` (`None` is a valid, explicit "first
    release" attestation value for this last key -- it is never merely
    absent-and-defaulted)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseHistoryAttestationError(f"{path}: not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ReleaseHistoryAttestationError(f"{path}: must be a JSON object")
    schema_version = data.get("schema_version")
    if schema_version != RELEASE_HISTORY_ATTESTATION_SCHEMA_VERSION:
        raise ReleaseHistoryAttestationError(
            f"{path}: unsupported schema_version {schema_version!r} (expected exactly "
            f"{RELEASE_HISTORY_ATTESTATION_SCHEMA_VERSION!r})"
        )
    required_keys = ("target_sha", "current_version", "previous_supported_version")
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        raise ReleaseHistoryAttestationError(f"{path}: missing required key(s): {', '.join(missing_keys)}")
    target_sha = data["target_sha"]
    if not isinstance(target_sha, str) or not re.fullmatch(r"^[0-9a-f]{40}$", target_sha):
        raise ReleaseHistoryAttestationError(f"{path}: 'target_sha' must be a 40-lowercase-hex commit SHA")
    current_version = data["current_version"]
    if not isinstance(current_version, str) or not VERSION_RE.fullmatch(current_version):
        raise ReleaseHistoryAttestationError(f"{path}: 'current_version' must be a MAJOR.MINOR.PATCH string")
    previous = data["previous_supported_version"]
    if previous is not None and (not isinstance(previous, str) or not VERSION_RE.fullmatch(previous)):
        raise ReleaseHistoryAttestationError(
            f"{path}: 'previous_supported_version' must be a MAJOR.MINOR.PATCH string or null"
        )
    return {"target_sha": target_sha, "current_version": current_version, "previous_supported_version": previous}


def check_release_tag_authority(
    repo_root: Path,
    target_sha: str,
    current_version: str,
    declared_previous_supported_version: Optional[str],
) -> List[str]:
    """The actual, fail-closed authority cross-check for a real git
    repository: the version ledger's own `previous_supported_version`
    (`declared_previous_supported_version`) is descriptive only -- this
    derives the true immediate predecessor purely from `target_sha`'s own
    reachable, immutable, annotated `expansion/MAJOR.MINOR.PATCH`
    release-tag history (`git_source.derive_release_predecessor`) and
    reports any disagreement. Also separately rejects the case where
    `current_version` itself already has a real release tag (a
    candidate must never reuse an already-tagged version), independent
    of whether that tag's own commit happens to equal `target_sha`."""
    errors: List[str] = []
    try:
        existing_current_tag = gs.find_release_tag_for_version(repo_root, current_version)
    except gs.ReleaseTagAuthorityError as error:
        return [str(error)]
    if existing_current_tag is not None:
        errors.append(
            f"an annotated release tag {existing_current_tag.ref!r} already exists for the current "
            f"candidate version {current_version!r} (commit {existing_current_tag.commit_sha!r}) -- "
            "this version has already been released; a release candidate must never reuse an "
            "already-tagged version"
        )
    try:
        authoritative_previous = gs.derive_release_predecessor(repo_root, target_sha, current_version)
    except gs.ReleaseTagAuthorityError as error:
        errors.append(str(error))
        return errors
    if declared_previous_supported_version != authoritative_previous:
        errors.append(
            f"version ledger previous_supported_version {declared_previous_supported_version!r} does "
            f"not match the true immediate predecessor {authoritative_previous!r} derived from this "
            "repository's own immutable, annotated 'expansion/MAJOR.MINOR.PATCH' release-tag "
            "history -- the ledger is descriptive only, never authoritative; correct/regenerate it "
            "to match real release-tag history (or, if none exists yet, declare null)"
        )
    return errors


def check_release_tag_authority_non_git(
    attestation_path: Optional[Path],
    target_sha: str,
    current_version: str,
    declared_previous_supported_version: Optional[str],
) -> List[str]:
    """The non-git/archive equivalent of `check_release_tag_authority`:
    a genuine extracted candidate tree has no local `.git` release-tag
    history to derive anything from at all, so an explicit, external,
    protected release-history attestation file -- bound to this exact
    `target_sha` and `current_version` -- is required instead. A missing
    attestation is its own explicit, actionable finding (never silently
    treated as a fabricated "no predecessor" pass); a present-but-
    mismatched/tampered attestation (wrong target SHA, wrong version, or
    a `previous_supported_version` that disagrees with the ledger's own
    descriptive claim) is reported just as explicitly."""
    if attestation_path is None:
        return [
            "no explicit, external, protected release-history attestation was supplied for this "
            "non-git candidate tree (--release-tag-attestation) -- a non-git materialization has no "
            "local, immutable annotated release-tag history to derive a true predecessor from, so a "
            "release-history authority fact can never be fabricated as an empty/absent history here; "
            "supply a real attestation file bound to this candidate's exact target SHA and version"
        ]
    try:
        attestation = load_release_history_attestation(Path(attestation_path))
    except ReleaseHistoryAttestationError as error:
        return [str(error)]
    errors: List[str] = []
    if attestation["target_sha"] != target_sha:
        errors.append(
            f"external release-history attestation {str(attestation_path)!r} is bound to target SHA "
            f"{attestation['target_sha']!r}, which does not match this candidate's own exact target "
            f"SHA {target_sha!r} -- an attestation bound to a different commit can never validate "
            "this candidate's release history"
        )
    if attestation["current_version"] != current_version:
        errors.append(
            f"external release-history attestation {str(attestation_path)!r} is bound to version "
            f"{attestation['current_version']!r}, which does not match this candidate's own current "
            f"version {current_version!r}"
        )
    if attestation["previous_supported_version"] != declared_previous_supported_version:
        errors.append(
            f"external release-history attestation {str(attestation_path)!r} declares "
            f"previous_supported_version {attestation['previous_supported_version']!r}, which does "
            f"not match the version ledger's own declared previous_supported_version "
            f"{declared_previous_supported_version!r} -- the ledger and the bound external "
            "attestation must agree exactly"
        )
    return errors


# --- Changelog SemVer-impact vs. actual version delta -----------------------


def classify_bump(previous_version: Optional[str], candidate_version: str) -> str:
    """Returns "initial" if there is no previous version to diff against
    (the bootstrap case -- never released before), else one of "none",
    "patch", "minor", "major". Raises `ConsistencyError` if `candidate_version`
    does not strictly increase over `previous_version` (versions must be
    monotonically increasing; this is never acceptable regardless of
    declared changelog impact)."""
    candidate_t = parse_version(candidate_version)
    if previous_version is None:
        return "initial"
    previous_t = parse_version(previous_version)
    if candidate_t == previous_t:
        return "none"
    if candidate_t < previous_t:
        raise ConsistencyError(
            f"candidate version {candidate_version!r} is not greater than previous supported "
            f"version {previous_version!r} (versions must increase monotonically)"
        )
    if candidate_t[0] != previous_t[0]:
        return "major"
    if candidate_t[1] != previous_t[1]:
        return "minor"
    return "patch"


def required_minimum_bump_rank(declared_impact: str, pre_1_0: bool) -> int:
    """The minimum version-delta "rank" (see BUMP_RANK) a given declared
    aggregate changelog `semver_impact` requires. Actually bumping *more*
    than the minimum is always fine (e.g. batching several releases'
    worth of change into one jump); bumping less is the contradiction
    this exists to catch.

    Pre-1.0, this project's docs/public_api_policy.md documents the
    standard SemVer pre-1.0 carve-out: MAJOR must stay 0, so both a
    breaking ("major"-impact) and an additive-but-compatible
    ("minor"-impact) change both require at least a MINOR bump (PATCH is
    reserved strictly for backward-compatible fixes) -- they collapse to
    the same minimum requirement pre-1.0. Post-1.0, "major" requires an
    actual MAJOR bump.
    """
    if declared_impact not in BUMP_RANK:
        raise ConsistencyError(f"unknown semver_impact {declared_impact!r}")
    if declared_impact == "major" and pre_1_0:
        return BUMP_RANK["minor"]
    return BUMP_RANK[declared_impact]


def check_changelog_semver_delta(
    previous_version: Optional[str],
    candidate_version: str,
    declared_impact: str,
    version_major: int,
) -> List[str]:
    """The changelog's aggregate declared `semver_impact` must not demand
    a *bigger* version bump than what the candidate version actually is
    relative to `previous_version` (a too-small bump, or a declared
    "major"/"minor" impact shipped as a bare patch bump, is exactly the
    "declared maximum changelog SemVer impact versus actual ... version
    delta" contradiction issue #9 requires this to reject)."""
    try:
        bump = classify_bump(previous_version, candidate_version)
    except ConsistencyError as error:
        return [str(error)]
    if bump == "initial":
        return []  # nothing to diff against yet -- the very first version.
    pre_1_0 = version_major == 0
    required_rank = required_minimum_bump_rank(declared_impact, pre_1_0)
    actual_rank = BUMP_RANK[bump]
    if actual_rank < required_rank:
        return [
            f"changelog aggregate declared semver_impact {declared_impact!r} requires at least a "
            f"{RANK_NAME[required_rank]!r}-level version bump from {previous_version!r} "
            f"({'pre-1.0' if pre_1_0 else 'post-1.0'} policy), but candidate version "
            f"{candidate_version!r} is only a {bump!r} bump"
        ]
    return []


# --- C fallback / packed / fingerprint metadata ------------------------------


def parse_c_fallback_header(text: str) -> Dict[str, str]:
    """Extracts every ``#define FE8_EXPANSION_<NAME> <value>`` line's raw
    (unparsed) value text. Since every one of these macros in
    include/expansion_config.h is guarded by its own ``#ifndef``, there is
    exactly one ``#define`` per name in the fallback header; the first
    match for a given name wins if that were ever violated."""
    values: Dict[str, str] = {}
    for line in text.splitlines():
        match = _DEFINE_LINE_RE.match(line)
        if match:
            values.setdefault(match.group(1), match.group(2))
    return values


def _c_string_literal(raw: str) -> Optional[str]:
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1]
    return None


def check_c_fallback_metadata(repo_root: Path, config_values: Dict[str, str]) -> List[str]:
    """Cross-checks include/expansion_config.h's ``#ifndef`` fallback
    literal defaults against config.mk's own resolved values (`config_values`,
    as returned by scripts/modernize/expansion_config.py's
    ``parse_config_mk``). That header's own comment already documents this
    invariant ("matching config.mk's own defaults exactly"); this is what
    mechanically enforces it."""
    header_path = Path(repo_root) / FALLBACK_HEADER_RELPATH
    if not header_path.is_file():
        return [f"{FALLBACK_HEADER_RELPATH} not found"]
    values = parse_c_fallback_header(header_path.read_text(encoding="utf-8"))
    errors: List[str] = []

    def expect_int(macro: str, config_key: str) -> None:
        if macro not in values:
            errors.append(f"{FALLBACK_HEADER_RELPATH}: missing '#define {macro}'")
            return
        try:
            actual = int(values[macro], 0)
        except ValueError:
            errors.append(
                f"{FALLBACK_HEADER_RELPATH}: {macro} fallback {values[macro]!r} is not an integer literal"
            )
            return
        try:
            expected = int(str(config_values[config_key]), 0)
        except (KeyError, ValueError):
            return
        if actual != expected:
            errors.append(
                f"{FALLBACK_HEADER_RELPATH}: {macro} fallback {actual} does not match config.mk "
                f"{config_key} {expected}"
            )

    def expect_string(macro: str, expected: Optional[str]) -> None:
        if expected is None:
            return
        if macro not in values:
            errors.append(f"{FALLBACK_HEADER_RELPATH}: missing '#define {macro}'")
            return
        literal = _c_string_literal(values[macro])
        if literal is None:
            errors.append(
                f"{FALLBACK_HEADER_RELPATH}: {macro} fallback {values[macro]!r} is not a quoted C string literal"
            )
            return
        if literal != expected:
            errors.append(
                f"{FALLBACK_HEADER_RELPATH}: {macro} fallback {literal!r} does not match expected {expected!r}"
            )

    expect_int("FE8_EXPANSION_VERSION_MAJOR", "EXPANSION_VERSION_MAJOR")
    expect_int("FE8_EXPANSION_VERSION_MINOR", "EXPANSION_VERSION_MINOR")
    expect_int("FE8_EXPANSION_VERSION_PATCH", "EXPANSION_VERSION_PATCH")
    expect_int("FE8_EXPANSION_ROM_REVISION", "EXPANSION_ROM_REVISION")
    expect_int("FE8_EXPANSION_SAVE_COMPAT_EPOCH", "EXPANSION_SAVE_COMPAT_EPOCH")

    expected_version_string = None
    try:
        major = int(str(config_values["EXPANSION_VERSION_MAJOR"]), 0)
        minor = int(str(config_values["EXPANSION_VERSION_MINOR"]), 0)
        patch = int(str(config_values["EXPANSION_VERSION_PATCH"]), 0)
        expected_version_string = f"{major}.{minor}.{patch}"
    except (KeyError, ValueError):
        pass
    expect_string("FE8_EXPANSION_VERSION_STRING", expected_version_string)
    expect_string("FE8_EXPANSION_ROM_TITLE", config_values.get("EXPANSION_ROM_TITLE"))
    expect_string("FE8_EXPANSION_ROM_GAME_CODE", config_values.get("EXPANSION_ROM_GAME_CODE"))
    expect_string("FE8_EXPANSION_ROM_MAKER_CODE", config_values.get("EXPANSION_ROM_MAKER_CODE"))

    fingerprint_raw = values.get(_FINGERPRINT_MACRO)
    if fingerprint_raw is None:
        errors.append(f"{FALLBACK_HEADER_RELPATH}: missing '#define {_FINGERPRINT_MACRO}'")
    else:
        literal = _c_string_literal(fingerprint_raw)
        if literal is None or not re.fullmatch(r"[0-9a-f]{16}", literal):
            errors.append(
                f"{FALLBACK_HEADER_RELPATH}: {_FINGERPRINT_MACRO} fallback {fingerprint_raw!r} must be a "
                "quoted, exactly-16-lowercase-hex-character placeholder"
            )

    return errors


# --- Save-format migration-registry epoch reachability -----------------------


def check_migration_epoch_reachability(current_epoch: int, registry) -> List[str]:
    """The migration registry must declare an unbroken chain of
    transitions from "no ExpansionSaveMeta record at all" (`epoch_from`
    ``None``) up to `current_epoch` -- i.e. config.mk's
    ``EXPANSION_SAVE_COMPAT_EPOCH`` must actually be *reachable* through
    the registry. Catches a future epoch bump that forgets to add its own
    registry entry (docs/migration_registry.md already documents this as
    a requirement; nothing mechanically enforced it before now) as well
    as a registry with a broken link in an otherwise longer chain."""
    reachable = {None}
    changed = True
    while changed:
        changed = False
        for step in registry:
            if step.epoch_from in reachable and step.epoch_to not in reachable:
                reachable.add(step.epoch_to)
                changed = True
    if current_epoch not in reachable:
        return [
            "no migration path from legacy/no-metadata (epoch None) to the current "
            f"EXPANSION_SAVE_COMPAT_EPOCH {current_epoch}; scripts/modernize/migrations/registry.py "
            "is missing a transition -- see docs/migration_registry.md"
        ]
    return []
