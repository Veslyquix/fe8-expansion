# Changelog

All notable changes to this project are documented here. This project is
currently pre-1.0 (see `config.mk`'s `EXPANSION_VERSION_*` and
[`docs/public_api_policy.md`](docs/public_api_policy.md) for exactly what
that means for SemVer/compatibility).

The `## [Unreleased]` section below is rendered **deterministically** from
machine-readable fragments in [`changelog_fragments/`](changelog_fragments/) by
`python3 -m scripts.release_rehearsal.changelog render` (or `write` to update this
file in place); see [`docs/release_process.md`](docs/release_process.md).
Do not hand-edit the text between the two HTML comment markers below --
`make release-check` fails actionably if it drifts from the fragments.

## [Unreleased]

<!-- release-rehearsal:unreleased:begin -->
### Fixed

- Fix a fresh, independent verifier-reproduced defect in the read-only release/publication rehearsal: `check`/`summary`/`rehearse` now route through one single, shared top-level exception boundary so a well-formed-but-nonexistent --target-sha (in a real git repository) and the documented non-git/extracted-candidate path (with or without its required exact 40-lowercase-hex --target-sha override) never traceback as an unhandled exception (which collided with EXIT_NOT_ELIGIBLE); both now fail actionably as EXIT_TOOLING_ERROR (2), while a well-formed extracted candidate genuinely produces canonical BLOCKED JSON end-to-end. `evaluate_rebuild_eligibility()` never invokes `git submodule status` (or any other git command) against a non-git repo-root, and a declared allowlist member with no on-disk representation at all is now a controlled, actionable refusal instead of a silent omission. Publication remains mechanically BLOCKED throughout; no new capability or eligibility change. (#9)

### Internal

- Add a read-only release/publication rehearsal system (policy, changelog fragments, release manifest, migration registry, source-release guard/provenance, deterministic archive rehearsal, and a read-only CI workflow); publication remains mechanically BLOCKED pending human license/provenance approval. (#9)
- Close a latent identity-confusion defect found in fresh review: a genuine non-git extracted release candidate nested inside an unrelated outer Git repository could have scripts/modernize/expansion_config.py's resolve_build_commit() silently adopt that outer repository's HEAD (via git's own upward directory discovery) as this candidate's internal build-commit identity, even though that field is not currently published. resolve_build_commit() now only ever invokes git when repo_root is itself bound to its own .git metadata; the release manifest (check/summary/rehearse) now threads the already-validated, exact target SHA (an explicit --target-sha override in non-git/archive mode, or the real repository's own resolved HEAD) into the embedded build identity as its single source of truth, so a nested non-git candidate never makes any git subprocess call and never substitutes the unresolved 'unknown' sentinel where the exact override is required. Publication remains mechanically BLOCKED throughout. (#9)
- Remediate a fresh, independent code review of the read-only release/publication rehearsal system: provenance coverage is now a literal, one-exact-record-per-allowlisted-member bijection (no directory-prefix/category inheritance, plus a submodule gitlink-pin cross-check) with a deterministic generator/checker; source_guard/archive_rehearsal candidate-membership checks (filesystem closed-world scan, archive members, and the non-git archive-build fallback) are exact-path-only, never directory-prefix; the workflow guard now rejects any permission scope granted write (not merely contents), including future-unknown scopes; and release.mk/release docs now correctly state that GNU Make collapses any failed recipe's exit code to 2, distinct from the underlying CLI's own 0/1/2/3 contract. Publication remains mechanically BLOCKED throughout. (#9)
- Remediate all ten independent-verifier findings against the read-only release/publication rehearsal system: exact per-member source allowlist and provenance coverage, expanded hard-deny rules with an audited map/hex exception list, immutable Git-blob-bound archive rehearsal, a truthful four-state rebuild rehearsal, additional manifest consistency validators, a machine-distinct exit/status contract, a dynamically-rendered CI job summary, a hardened workflow guard, and fixed broken docs links; publication remains mechanically BLOCKED throughout. (#9)
<!-- release-rehearsal:unreleased:end -->

## [0.1.0] - baseline

The framework's semantic version and GBA ROM identity fields were
established in `config.mk` (issue #8) before this changelog/fragment
system existed; no fragment history is recorded for it. See
`docs/config_identity.md`.
